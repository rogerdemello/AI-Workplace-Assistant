from fastapi import status


def test_unified_chat_response_includes_flow_metadata_for_ticket_flow(client, auth_headers):
    response = client.post(
        "/api/v1/chat/message",
        headers=auth_headers,
        json={"message": "I want to raise a complaint"},
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()

    flow_metadata = payload.get("flow_metadata")
    assert isinstance(flow_metadata, dict)
    assert flow_metadata.get("flow_name") == "ticket"
    assert flow_metadata.get("step")
    assert "missing_fields" in flow_metadata
    assert flow_metadata.get("completed") is False


def test_unified_chat_response_has_empty_flow_metadata_for_general_query(client, auth_headers):
    response = client.post(
        "/api/v1/chat/message",
        headers=auth_headers,
        json={"message": "hello there"},
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()

    flow_metadata = payload.get("flow_metadata")
    assert isinstance(flow_metadata, dict)
    assert flow_metadata.get("flow_name") is None
    assert flow_metadata.get("missing_fields") == []
