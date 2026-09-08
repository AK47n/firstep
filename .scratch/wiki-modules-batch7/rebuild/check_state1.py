# -*- coding: utf-8 -*-
"""验证当前三平台文件处于 state1（commit 01 mq135 状态）。"""
import json

m = open("library/masters/mspm0/mspm0.syscfg", encoding="utf-8").read()
i = open("src/contest_generator/syscfg_instances.py", encoding="utf-8").read()
w = open("src/contest_generator/wordlist.json", encoding="utf-8").read()

ok = True
def chk(label, cond):
    global ok
    print(("OK  " if cond else "BAD ") + label)
    ok = ok and cond

chk("master endAdd=4", 'ADC12_0.endAdd                     = 4;' in m)
chk("master MEM4 CHAN_6", 'ADC12_0.adcMem4chansel             = "DL_ADC12_INPUT_CHAN_6";' in m)
chk("master adcPin6=PB20", 'ADC12_0.peripheral.adcPin6.$assign = "PB20";' in m)
chk("master 无 MEM5", "adcMem5chansel" not in m)
chk("master 无 adcPin5", "adcPin5.$assign" not in m)
chk("master 无 SGP30 实例", "const SGP30" not in m)
chk("master 无 AGS10 实例", "const AGS10" not in m)
chk("inst ADC 元组含 mq135 不含 mq5", '"ADC12_0": ("adc", "joystick", "us016", "ir_distance", "mq2", "mq135"),' in i)
chk("inst 无 SGP30/AGS10 行", '"SGP30": (' not in i and '"AGS10": (' not in i)
data = json.loads(w)
sols = []
models = []
for g in data:
    if g.get("category") == "感知传感器":
        sols = [s["name"] for s in g.get("solutions", [])]
        models = list(g["models"])
chk("wordlist 有 MQ-135", any("MQ-135" in s for s in sols))
chk("wordlist 无 MQ-5/SGP30/AGS10 方案", not any(("MQ-5" in s or "SGP30" in s or "AGS10" in s) for s in sols))
chk("wordlist models 无 MQ-5", "MQ-5" not in models)
chk("wordlist models 有 MQ-135", "MQ-135" in models)
print("STATE1 " + ("OK" if ok else "FAIL"))
