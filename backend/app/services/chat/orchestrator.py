"""Single conversation brain: intent, flows, specialist dispatch, optional multi-agent overlays.

When ENABLE_MULTI_AGENT_ORCHESTRATION is true, supplementary agents (analysis, emotional,
proactive) layer on the primary reply via agent_router → agent_executor → response_merger.
HR / life / productivity flows remain in _dispatch and v2 agents unless extended."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ...services.hr_personality import detect_conversation_mode
from ...services.health_detector import detect_health_keywords
from ...services.v2.capabilities import get_capabilities
from ...services.v2.life_assistant_agent import LifeAssistantAgent
from ...services.v2.productivity_agent import ProductivityAgent
from ...config import settings
from .contracts import AgentTurnContext, FlowStateContract
from .flow_manager import FlowManager
from .slot_filler import fill_slots


class ConversationOrchestrator:
    def __init__(self, smart_service: Any):
        self.service = smart_service
        self.flow_manager = FlowManager()
        self.capabilities = get_capabilities()
        self.life_agent = LifeAssistantAgent(db=self.service.db, user_id=self.service.user_id)
        self.productivity_agent = ProductivityAgent(db=self.service.db, user_id=self.service.user_id)

    def run(self, message: str) -> Dict[str, Any]:
        if not message or not message.strip():
            return self.service._empty_message_response()

        _fast = bool(settings.FAST_CHAT_MODE)

        from .compound_intent import analyze_compound

        self.service.flow_context["_mark_compound"] = analyze_compound(message).to_dict()

        if getattr(settings, "ENABLE_MARK_INTELLIGENCE_PIPELINE", False) and not getattr(
            settings, "CHAT_SKIP_INTELLIGENCE_SNAPSHOT", False
        ):
            from ..intelligence.sentiment_service import analyze_user_message_intelligence

            snap = analyze_user_message_intelligence(message)
            if snap:
                self.service.flow_context["_intelligence_sentiment"] = snap

        message_stripped = message.strip().lower()
        strong_intent = self.service._detect_strong_intent(message)
        intent = self._resolve_intent(message, message_stripped, strong_intent)

        if not self.service.current_flow and self.service._is_greeting(message):
            if not self.service.flow_context.get("has_greeted"):
                intent = "greeting"

        intel_ctx = self.service.flow_context.get("_intelligence_sentiment")
        if intel_ctx:
            s0 = int(intel_ctx.get("score_0_100", 50))
            sentiment_result = {
                "sentiment": str(intel_ctx.get("label", "neutral")),
                "score": max(-1.0, min(1.0, (s0 - 50) / 50.0)),
            }
        elif _fast:
            # FAST_CHAT_MODE: lexicon-only on the reply path for every message —
            # the hybrid analyze() makes an LLM call (up to SENTIMENT_LLM_TIMEOUT
            # seconds) and is redundant here, since the HR-persisted sentiment is
            # already lexicon (CHAT_SYNC_LEXICON_SENTIMENT) and this value only
            # drives conversation-mode detection.
            sentiment_result = self.service.sentiment_service.analyze_lexicon_only(message)
        else:
            sentiment_result = self.service.sentiment_service.analyze(message)
        sentiment = sentiment_result.get("sentiment", "neutral")

        mode = detect_conversation_mode(intent=intent, sentiment=sentiment, message=message)
        if self.service.current_flow in {"ticket", "leave_request"} or (
            self.service.current_flow in self.flow_manager.SLOT_FLOWS
        ):
            mode = "action"
        self.service.conversation_mode = mode
        self.service.flow_context["conversation_mode"] = mode

        if not self.service.current_flow:
            flow_name = self.flow_manager.flow_for_intent(intent)
            if flow_name:
                self.service.current_flow = flow_name
                self.service.flow_context["pending_intent"] = intent

        response_text = self._dispatch(message=message, intent=intent, sentiment=sentiment, mode=mode)
        response_text = self._apply_multi_agent_layers(
            message=message,
            intent=intent,
            sentiment=sentiment,
            primary_reply=response_text,
        )
        switch_from = self.service.flow_context.pop("switch_from_flow", None)
        switch_to = self.service.flow_context.pop("switch_to_intent", None)
        if switch_from and switch_to:
            ack = self.service._build_intent_switch_ack(switch_from, switch_to)
            response_text = f"{ack} {response_text}"

        if not _fast and intent not in ["policy_query", "benefits_question"]:
            response_text = self.service._compress_response(response_text, intent, sentiment)

        response_text = self.service._finalize_response(
            response_text,
            intent,
            sentiment,
            mode,
            source_message=message,
        )
        response_text = self.service._deduplicate_response(response_text)

        self.service.previous_intent = intent
        self.service._update_conversation_state(intent, message)
        self.service._update_memory(message, intent, sentiment)
        self.service._save_flow_state()

        health_result = detect_health_keywords(message)

        context_payload = dict(self.service.user_context)
        context_payload["conversation_mode"] = mode
        context_payload["active_flow"] = self.service.current_flow
        flow_metadata = self._build_flow_metadata(intent=intent)

        return {
            "response": response_text,
            "intent": intent,
            "sentiment": sentiment,
            "conversation_state": self.service.conversation_state,
            "context": context_payload,
            "flow_metadata": flow_metadata,
            "health_detected": health_result,
        }

    def _resolve_intent(self, message: str, message_stripped: str, strong_intent: Optional[str]) -> str:
        # If in a flow and user sends short input (yes/no/date), treat as answering current question
        if self.service.current_flow and self.service._is_short_input(message_stripped):
            return self.service.previous_intent or self.service.flow_context.get("pending_intent", "general_query")

        if self.service.current_flow:
            if strong_intent:
                new_flow = self.flow_manager.flow_for_intent(strong_intent)
                current_flow_intent = self.service.flow_context.get("pending_intent")

                if strong_intent in {"leave_balance"}:
                    self.service._reset_flow()
                    return strong_intent

                if new_flow and new_flow != self.service.current_flow:
                    # Switching to a different flow - reset and start fresh
                    from_flow = self.service.current_flow
                    self.service._reset_flow()
                    self.service.flow_context["switch_from_flow"] = from_flow
                    self.service.flow_context["switch_to_intent"] = strong_intent
                    self.service.current_flow = new_flow
                    self.service.flow_context["pending_intent"] = strong_intent
                    return strong_intent
                
                # Same flow or no flow - continue with strong intent but reset context
                if not new_flow:
                    # Strong intent that doesn't map to any flow (e.g., "joke", "hello")
                    # Reset current flow to allow natural conversation
                    self.service._reset_flow()
                    return strong_intent

                return self.service.previous_intent or current_flow_intent or "general_query"

            # No strong intent detected but we're in a flow
            # Classify the message to see if user wants to do something else
            intent_result = self.service.intent_classifier.classify(message, str(self.service.user_id))
            classified = intent_result.get("intent", "general_query")
            classified = self.service._apply_intent_keyword_fallback(classified, message)
            
            # If classified intent is different from current flow intent and not a flow continuation
            current_flow_name = self.service.current_flow
            expected_flow = self.flow_manager.flow_for_intent(classified)
            
            if expected_flow != current_flow_name and classified not in {"general_query", "greeting"}:
                # User wants to do something different - reset flow
                self.service._reset_flow()
                return classified
            
            # Continue current flow
            return self.service.previous_intent or self.service.flow_context.get("pending_intent", "general_query")

        if strong_intent:
            return strong_intent

        intent_result = self.service.intent_classifier.classify(message, str(self.service.user_id))
        classified = intent_result.get("intent", "general_query")
        return self.service._apply_intent_keyword_fallback(classified, message)

    def _dispatch(self, *, message: str, intent: str, sentiment: str, mode: str) -> str:
        flow_name = self.service.current_flow
        if flow_name in {"ticket", "leave_request"}:
            return self._run_flow(flow_name=flow_name, intent=intent, message=message)
        if flow_name in self.flow_manager.SLOT_FLOWS:
            return self._run_slot_flow(flow_name=flow_name, intent=intent, message=message)

        if intent == "greeting":
            if self.service.flow_context.get("has_greeted"):
                return "What can I help you with?"
            self.service.flow_context["has_greeted"] = True
            return self.service._handle_greeting(sentiment, mode)
        if intent == "resignation_support":
            return self.service._handle_resignation_support(message)
        if intent == "leave_balance":
            return self.service._handle_leave_balance()
        if intent == "reminder":
            return self.service._handle_reminder(message)
        if intent == "help_request":
            return self.service._handle_help_request(message)
        if intent == "policy_query":
            return self.service._handle_policy_query(message)
        if intent == "benefits_question":
            return self.service._handle_benefits_query(message)
        if intent == "email_draft":
            return self.service._handle_email_draft(message)
        if intent == "appreciation":
            return self.service._handle_appreciation(message)
        if intent == "escalate_ticket":
            return self.service._handle_escalate_ticket()
        if intent == "emotional":
            return self.service._handle_emotional(message, sentiment)

        if intent == "general_query":
            if self.capabilities.enable_life_assistant:
                life_response = self.life_agent.maybe_handle(message)
                if life_response.handled:
                    return life_response.reply
            if self.capabilities.enable_productivity_agent:
                productivity_response = self.productivity_agent.maybe_handle(message, self.service.flow_context)
                if productivity_response.handled:
                    return productivity_response.reply
            fast = self.service._try_fast_intent_reply(message)
            if fast:
                return fast

        faq_answer = self.service.detect_faq(message)
        if faq_answer:
            return faq_answer
        
        return self.service._handle_general_query(message, sentiment, mode)

    def _run_flow(self, *, flow_name: str, intent: str, message: str) -> str:
        if flow_name == "leave_request":
            self.service.flow_context["pending_intent"] = "leave_request"
            contract_model = FlowStateContract.from_state(
                self.service.flow_context.get("state_contract"), intent=intent
            )
            if not contract_model.data and self.service.flow_context.get("leave_data"):
                contract_model.data = dict(self.service.flow_context.get("leave_data") or {})
            contract = contract_model.model_dump()
            data_snapshot = dict(contract.get("data") or {})

            if self.service.flow_context.get("last_question") == "confirm":
                parsed = self.service._parse_yes_no(message)
                if parsed is True:
                    return self.service._complete_leave(data_snapshot)
                if parsed is False:
                    return "No problem — tell me what you'd like to change, or say when you're ready to submit."

            if self.service.flow_context.get("leave_long_duration_warning_shown"):
                parsed = self.service._parse_yes_no(message)
                if parsed is True:
                    self.service.flow_context.pop("leave_long_duration_warning_shown", None)
                    self.service.flow_context["leave_long_duration_confirmed"] = True
                    return self.service._complete_leave(data_snapshot)
                if parsed is False:
                    self.service._reset_flow()
                    return "Got it, I won't submit the long leave request."

            if self.service.flow_context.get("leave_overlap_warning_shown"):
                parsed = self.service._parse_yes_no(message)
                if parsed is True:
                    self.service.flow_context.pop("leave_overlap_warning_shown", None)
                    cont = FlowStateContract.from_state(
                        self.service.flow_context.get("state_contract"), intent=intent
                    ).model_dump()
                    if not cont.get("data") and self.service.flow_context.get("leave_data"):
                        cont["data"] = dict(self.service.flow_context.get("leave_data") or {})
                    d = dict(cont.get("data") or {})
                    next_step = self.flow_manager.next_step(
                        flow_name, d, self.service.flow_context, last_question=None
                    )
                    cont["step"] = next_step
                    cont["completed"] = False
                    self.service.flow_context["state_contract"] = cont
                    self.service.flow_context["last_question"] = next_step
                    return self.flow_manager.prompt_for_step(flow_name, next_step, d)
                if parsed is False:
                    self.service._reset_flow()
                    return "Got it, I won't submit the overlapping leave request."

            extracted = self.service.entity_extractor.extract_leave_entities(
                message,
                current_data=contract.get("data"),
            )
            filled = fill_slots(
                self.flow_manager,
                flow_name=flow_name,
                state=contract,
                extracted_slots=extracted,
            )
            contract = filled.state
            self.service.flow_context["leave_data"] = dict(contract["data"])

            if "invalid_start_date" in filled.errors or "invalid_end_date" in filled.errors:
                contract["step"] = "start_date"
                self.service.flow_context["state_contract"] = contract
                return "Please use valid dates in YYYY-MM-DD format."

            last_question = self.service.flow_context.get("last_question")
            next_step = self.flow_manager.next_step(
                flow_name, contract["data"], self.service.flow_context, last_question=last_question
            )
            if next_step == last_question and next_step != "done":
                contract["data"][next_step] = contract["data"].get(next_step, "unspecified")
                next_step = self.flow_manager.next_step(
                    flow_name, contract["data"], self.service.flow_context, last_question=last_question
                )
            contract["step"] = next_step
            contract["completed"] = False
            self.service.flow_context["state_contract"] = contract

            # Overlap: only after both dates are present and valid
            d = contract["data"]
            if (
                not self.service.flow_context.get("leave_overlap_warning_shown")
                and self.flow_manager._missing_leave_date(d, "start_date") is False
                and self.flow_manager._missing_leave_date(d, "end_date") is False
                and next_step not in ("end_date_invalid", "max_duration_exceeded", "start_date_invalid")
            ):
                overlapping = self.service._check_leave_overlap(d)
                if overlapping:
                    self.service.flow_context["leave_overlap_warning_shown"] = True
                    self.service.flow_context["last_question"] = "overlap_warning"
                    return (
                        f"You already have leave from {overlapping.start_date} "
                        f"to {overlapping.end_date}. Do you still want to proceed?"
                    )

            self.service.flow_context["last_question"] = next_step
            return self.flow_manager.prompt_for_step(flow_name, next_step, contract["data"])

        self.service.flow_context["pending_intent"] = "ticket_create"
        contract_model = FlowStateContract.from_state(
            self.service.flow_context.get("state_contract"), intent=intent
        )
        if not contract_model.data and self.service.flow_context.get("ticket_data"):
            contract_model.data = dict(self.service.flow_context.get("ticket_data") or {})
        contract = contract_model.model_dump()
        ticket_snapshot = dict(contract.get("data") or {})

        if self.service.flow_context.get("last_question") == "confirm":
            parsed = self.service._parse_yes_no(message)
            if parsed is True:
                return self.service._complete_ticket(ticket_snapshot)
            if parsed is False:
                return "No problem — tell me what to change, or say when you're ready to send it."

        extracted = self.service.entity_extractor.extract_ticket_entities(message)
        derived: Dict[str, Any] = {}
        message_lower = message.lower()

        if not contract["data"].get("department"):
            if any(word in message_lower for word in ["manager", "boss", "team lead", "supervisor"]):
                derived["department"] = "HR"
            elif any(word in message_lower for word in ["laptop", "computer", "wifi", "software", "printer", "access"]):
                derived["department"] = "IT"
            elif any(word in message_lower for word in ["office", "desk", "parking", "clean", "food"]):
                derived["department"] = "Facilities"

        if not contract["data"].get("issue") and not extracted.get("issue") and self.service._looks_like_ticket_issue(message):
            derived["issue"] = message.strip()

        if not contract["data"].get("category"):
            derived["category"] = extracted.get("category") or "complaint"

        parsed_choice = self.service._parse_yes_no(message)
        if (
            parsed_choice is not None
            and contract["data"].get("anonymous") is None
            and self.service.flow_context.get("last_question") == "anonymous"
        ):
            derived["anonymous"] = parsed_choice

        extracted.update(derived)

        filled = fill_slots(
            self.flow_manager,
            flow_name=flow_name,
            state=contract,
            extracted_slots=extracted,
        )
        contract = filled.state
        self.service.flow_context["ticket_data"] = dict(contract["data"])

        last_question = self.service.flow_context.get("last_question")
        next_step = self.flow_manager.next_step(
            flow_name, contract["data"], self.service.flow_context, last_question=last_question
        )
        if next_step == last_question and next_step != "done":
            contract["data"][next_step] = contract["data"].get(next_step, "unspecified")
            next_step = self.flow_manager.next_step(
                flow_name, contract["data"], self.service.flow_context, last_question=last_question
            )
        contract["step"] = next_step
        contract["completed"] = False

        if next_step == "anonymous":
            self.service.flow_context["_anon_asked"] = True

        self.service.flow_context["state_contract"] = contract
        self.service.flow_context["last_question"] = next_step
        return self.flow_manager.prompt_for_step(flow_name, next_step, contract["data"])

    #: Validation errors that should re-ask a slot instead of advancing the flow.
    _SLOT_ERROR_STEPS = {
        "invalid_preferred_date": "preferred_date",
        "invalid_preferred_time": "preferred_time_invalid",
        "invalid_expense_date": "expense_date_invalid",
        "invalid_amount": "amount_invalid",
        "invalid_start_date": "start_date",
        "invalid_end_date": "end_date",
    }

    def _run_slot_flow(self, *, flow_name: str, intent: str, message: str) -> str:
        """Generic collect → confirm → submit loop for the employee-request flows."""
        self.service.flow_context["pending_intent"] = intent

        contract_model = FlowStateContract.from_state(
            self.service.flow_context.get("state_contract"), intent=intent
        )
        stashed = self.service.flow_context.get("request_data")
        if not contract_model.data and stashed:
            contract_model.data = dict(stashed)
        contract = contract_model.model_dump()

        if self.service.flow_context.get("last_question") == "confirm":
            parsed = self.service._parse_yes_no(message)
            if parsed is True:
                return self.service._complete_employee_request(
                    flow_name, dict(contract.get("data") or {})
                )
            if parsed is False:
                return "No problem — tell me what you'd like to change, or say when you're ready to submit."

        extracted = self.service.entity_extractor.extract_request_entities(
            flow_name,
            message,
            current_data=contract.get("data"),
        )
        filled = fill_slots(
            self.flow_manager,
            flow_name=flow_name,
            state=contract,
            extracted_slots=extracted,
        )
        contract = filled.state
        self.service.flow_context["request_data"] = dict(contract["data"])

        for error in filled.errors:
            step = self._SLOT_ERROR_STEPS.get(error)
            if step:
                contract["step"] = step
                self.service.flow_context["state_contract"] = contract
                self.service.flow_context["last_question"] = step
                return self.flow_manager.prompt_for_step(flow_name, step, contract["data"])

        last_question = self.service.flow_context.get("last_question")
        next_step = self.flow_manager.next_step(
            flow_name, contract["data"], self.service.flow_context, last_question=last_question
        )
        contract["step"] = next_step
        contract["completed"] = False
        self.service.flow_context["state_contract"] = contract
        self.service.flow_context["last_question"] = next_step
        return self.flow_manager.prompt_for_step(flow_name, next_step, contract["data"])

    def _apply_multi_agent_layers(
        self,
        *,
        message: str,
        intent: str,
        sentiment: str,
        primary_reply: str,
    ) -> str:
        """Layer analysis / emotional / proactive specialists on top of the primary reply."""
        if not getattr(settings, "ENABLE_MULTI_AGENT_ORCHESTRATION", False):
            return primary_reply
        try:
            from ..agents.base import AgentContext
            from .agent_executor import execute_supplementary_agents
            from .agent_router import AgentRouter
            from .response_merger import merge_supplementary

            router = AgentRouter()
            plan = router.plan(message=message, intent=intent, sentiment=sentiment, orchestrator=self)
            self.service.flow_context["_mark_orchestrator_decision"] = plan.decision.model_dump()
            turn_context = AgentTurnContext(
                message=message,
                intent=intent,
                sentiment=sentiment,
                user_id=self.service.user_id,
                active_flow=self.service.current_flow,
                conversation_mode=self.service.conversation_mode,
            )
            self.service.flow_context["_mark_turn_context"] = turn_context.model_dump()
            ctx = AgentContext(
                message=message,
                intent=intent,
                sentiment=sentiment,
                user_id=self.service.user_id,
                orchestrator=self,
            )
            results, envelope = execute_supplementary_agents(plan.supplementary, ctx)
            self.service.flow_context["_mark_execution_envelope"] = envelope.model_dump()
            return merge_supplementary(primary_reply, results, original_message=message)
        except Exception:
            return primary_reply

    def _build_flow_metadata(self, *, intent: str) -> Dict[str, Any]:
        flow_name = self.service.current_flow
        contract = self.service.flow_context.get("state_contract", {}) or {}
        data = contract.get("data") if isinstance(contract, dict) else {}
        step = contract.get("step") if isinstance(contract, dict) else None
        completed = bool(contract.get("completed", False)) if isinstance(contract, dict) else False

        missing_fields: list[str] = []
        if flow_name:
            missing_fields = self.flow_manager.missing_fields(flow_name, data if isinstance(data, dict) else {})

        return {
            "flow_name": flow_name,
            "intent": intent,
            "step": step,
            "missing_fields": missing_fields,
            "collected_fields": sorted(list((data or {}).keys())) if isinstance(data, dict) else [],
            "completed": completed,
        }
