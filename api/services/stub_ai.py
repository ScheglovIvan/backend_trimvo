import time
import random
from core.config import get_settings

settings = get_settings()


def run_stub_generation(latency_ms: int, success_rate: float) -> tuple[bool, str]:
    time.sleep(latency_ms / 1000.0)
    success = random.random() < success_rate
    if success:
        return True, "templates/mock_result.mp4"
    return False, "Stub failure simulation"
