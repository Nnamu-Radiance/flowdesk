import os
import sys
from pathlib import Path

# Fix sys.path to prioritize the service-specific apps directory
# This prevents root-level "apps" from shadowing local service apps
service_root = Path(__file__).resolve().parent.parent
project_root = service_root.parent.parent

if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
