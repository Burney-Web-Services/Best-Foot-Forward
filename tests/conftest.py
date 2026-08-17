"""
Mock heavy ML dependencies so transcribe.py can be imported during tests
without triggering sys.exit(1) on missing audio packages.
"""
import sys
from unittest.mock import MagicMock

# Stub faster-whisper and pyannote before any test imports transcribe
sys.modules.setdefault('faster_whisper', MagicMock())
sys.modules.setdefault('pyannote', MagicMock())
sys.modules.setdefault('pyannote.audio', MagicMock())

# Stub torch with CUDA disabled so transcribe.py's device-detection logic
# stays on CPU without raising comparison errors against MagicMock values.
mock_torch = MagicMock()
mock_torch.cuda.is_available.return_value = False
sys.modules['torch'] = mock_torch
