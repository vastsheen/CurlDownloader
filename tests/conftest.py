"""让 tests/ 下的用例无需安装包即可导入 curldownloader。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
