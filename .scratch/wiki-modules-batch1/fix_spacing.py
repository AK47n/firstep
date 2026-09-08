# -*- coding: utf-8 -*-
p = "library/masters/mspm0/mspm0.syscfg"
t = open(p, encoding="utf-8", newline="").read()
old = 'JOYSTICK.associatedPins[0].pin.$assign      = "PA9";'
new = 'JOYSTICK.associatedPins[0].pin.$assign  = "PA9";'
assert old in t
open(p, "w", encoding="utf-8", newline="").write(t.replace(old, new, 1))
print("OK")
