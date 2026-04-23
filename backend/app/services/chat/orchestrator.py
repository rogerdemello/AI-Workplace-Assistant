"""Single conversation brain: orchestrates intent, slots, validation, actions, and response."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ...services.hr_personality import detect_conversation_mode
from ...services.health_detector import detect_health_keywords
from .flow_manager import FlowManager
from .slot_filler import fill_slots


class ConversationOrchestrator:
    def __init__(self, smart_service: Any):
        self.service = smart_service
        self.flow_manager = FlowManager()

    def run(self, message: str) -> Dict[str, Any]:
        if not message or not message.strip():
            return self.service._empty_message_response()

        message_stripped = message.strip().lower()
        strong_intent = self.service._detect_strong_intent(message)
        intent = self._resolve_intent(message, message_stripped, strong_intent)

        if not self.service.current_flow and self.service._is_greeting(message):
            if not self.service.flow_context.get("has_greeted"):
                intent = "greeting"

        sentiment_result = self.service.sentiment_service.analyze(message)
        sentiment = sentiment_result.get("sentiment", "neutral")

        mode = detect_conversation_mode(intent=intent, sentiment=sentiment, message=message)
        if self.service.current_flow in {"ticket", "leave_request"}:
            mode = "action"
        self.service.conversation_mode = mode
        self.service.flow_context["conversation_mode"] = mode

        if not self.service.current_flow:
            flow_name = self.flow_manager.flow_for_intent(intent)
            if flow_name:
                self.service.current_flow = flow_name
                self.service.flow_context["pending_intent"] = intent

        response_text = self._dispatch(message=message, intent=intent, sentiment=sentiment, mode=mode)

        if intent not in ["policy_query", "benefits_question"]:
            response_text = self.service._compress_response(response_text, intent, sentiment)

        response_text = self.service._finalize_response(response_text, intent, sentiment, mode)
        response_text = self.service._deduplicate_response(response_text)

        self.service.previous_intent = intent
        self.service._update_conversation_state(intent, message)
        self.service._update_memory(message, intent, sentiment)
        self.service._save_flow_state()

        health_result = detect_health_keywords(message)

        context_payload = dict(self.service.user_context)
        context_payload["conversation_mode"] = mode
        context_payload["active_flow"] = self.service.current_flow

        return {
            "response": response_text,
            "intent": intent,
            "sentiment": sentiment,
            "conversation_state": self.service.conversation_state,
            "context": context_payload,
            "health_detected": health_result,
        }

    def _resolve_intent(self, message: str, message_stripped: str, strong_intent: Optional[str]) -> str:
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
                    contract = self.service.flow_context.get("state_contract", {})
                    if not contract.get("completed", False):
                        return self.service.previous_intent or current_flow_intent or "general_query"
                    self.service.current_flow = new_flow
                    self.service.flow_context["pending_intent"] = strong_intent
                    return strong_intent

                return self.service.previous_intent or current_flow_intent or "general_query"

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

        if intent == "greeting":
            if self.service.flow_context.get("has_greeted"):
                return "What can I help you with?"
            self.service.flow_context["has_greeted"] = True
            return self.service._handle_greeting(sentiment, mode)
        if intent == "leave_balance":
            return self.service._handle_leave_balance()
        if intent == "reminder":
            return self.service._handle_reminder(message)
        if intent == "help_request":
            return self.service._handle_help_request()
        if intent == "policy_query":
            return self.service._handle_policy_query(message)
        if intent == "benefits_question":
            return self.service._handle_benefits_query(message)
        if intent == "email_draft":
            return self.service._handle_email_draft(message)
        if intent == "escalate_ticket":
            return self.service._handle_escalate_ticket()
        if intent == "emotional":
            return self.service._handle_emotional(message, sentiment)

        faq_answer = self.service.detect_faq(message)
        if faq_answer:
            return faq_answer
        
        return self.service._handle_general_query(message, sentiment, mode)

    def _run_flow(self, *, flow_name: str, intent: str, message: str) -> str:
        if flow_name == "leave_request":
            self.service.flow_context["pending_intent"] = "leave_request"
            contract = self.flow_manager.ensure_state_contract(
                self.service.flow_context.get("state_contract"), intent=intent
            )
            if not contract["data"] and self.service.flow_context.get("leave_data"):
                contract["data"] = dict(self.service.flow_context.get("leave_data") or {})

            extracted = self.service.entity_extractor.extract_leave_entities(message)
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
            contract["completed"] = next_step == "done"
            self.service.flow_context["state_contract"] = contract
            self.service.flow_context["last_question"] = next_step

            if next_step == "done":
                # Handle overlap confirmation from previous warning
                if self.service.flow_context.get("leave_overlap_warning_shown"):
                    parsed = self.service._parse_yes_no(message)
                    if parsed is True:
                        self.service.flow_context.pop("leave_overlap_warning_shown", None)
                        return self.service._complete_leave(contract["data"])
                    elif parsed is False:
                        self.service._reset_flow()
                        return "Got it, I won't submit the overlapping leave request."
                    else:
                        overlapping = self.service._check_leave_overlap(contract["data"])
                        if overlapping:
                            return (
                                f"You already have leave from {overlapping.start_date} "
                                f"to {overlapping.end_date}. Do you still want to proceed?"
                            )
                        self.service.flow_context.pop("leave_overlap_warning_shown", None)
                        return self.service._complete_leave(contract["data"])

                overlapping = self.service._check_leave_overlap(contract["data"])
                if overlapping:
                    self.service.flow_context["leave_overlap_warning_shown"] = True
                    contract["completed"] = False
                    self.service.flow_context["state_contract"] = contract
                    return (
                        f"You already have leave from {overlapping.start_date} "
                        f"to {overlapping.end_date}. Do you still want to proceed?"
                    )

                return self.service._complete_leave(contract["data"])
            return self.flow_manager.prompt_for_step(flow_name, next_step, contract["data"])

        self.service.flow_context["pending_intent"] = "ticket_create"
        contract = self.flow_manager.ensure_state_contract(
            self.service.flow_context.get("state_contract"), intent=intent
        )
        if not contract["data"] and self.service.flow_context.get("ticket_data"):
            contract["data"] = dict(self.service.flow_context.get("ticket_data") or {})

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

        severity = self.service._extract_ticket_severity(message)
        if severity and not contract["data"].get("severity"):
            derived["severity"] = severity

        parsed_choice = self.service._parse_yes_no(message)
        if parsed_choice is not None and contract["data"].get("anonymous") is None:
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

        if "invalid_severity" in filled.errors:
            contract["step"] = "severity"
            self.service.flow_context["state_contract"] = contract
            return "Please pick a severity: mild, serious, or urgent."

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
        contract["completed"] = next_step == "done"

        if next_step == "anonymous":
            self.service.flow_context["_anon_asked"] = True

        self.service.flow_context["state_contract"] = contract
        self.service.flow_context["last_question"] = next_step
        if next_step == "done":
            return self.service._complete_ticket(contract["data"])
        return self.flow_manager.prompt_for_step(flow_name, next_step, contract["data"])
