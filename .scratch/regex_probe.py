import sys
sys.path.insert(0, r'.claude\worktrees\syscfg-prune-01\src')
from contest_generator.syscfg_prune import _INSTANCE_DECL_RE, _MODULE_DECL_RE
lines = [
    'const IMU601  = UART.addInstance();',
    'const UART    = scripting.addModule("/ti/driverlib/UART", {}, false);',
    'IMU601.$name             = "IMU601";',
]
for l in lines:
    print(repr(l), bool(_INSTANCE_DECL_RE.match(l)), bool(_MODULE_DECL_RE.match(l)))
