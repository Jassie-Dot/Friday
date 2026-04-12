from core.intent import is_conversational


def test_short_greeting_routes_to_conversation():
    assert is_conversational("hello there")


def test_task_request_routes_to_execution():
    assert not is_conversational("run the build and open the logs")
