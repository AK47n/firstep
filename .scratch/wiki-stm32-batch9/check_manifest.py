import json
import sys

a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))

def same_mspm0(a, b):
    pa, pb = a["platforms"]["mspm0"], b["platforms"]["mspm0"]
    if a["dependencies"] != b["dependencies"]:
        print("deps differ", a["dependencies"], b["dependencies"])
    else:
        print("deps same")
    if pa != pb:
        print("mspm0 entries DIFFER")
        for k in pa:
            if pa[k] != pb.get(k):
                print("  key differs:", k)
                if isinstance(pa[k], str) and isinstance(pb.get(k), str):
                    sa, sb = pa[k], pb.get(k)
                    for i, (x, y) in enumerate(zip(sa.split("\n"), sb.split("\n"))):
                        if x != y:
                            print("   line", i, "A:", x[:120])
                            print("   line", i, "B:", y[:120])
                            break
    else:
        print("mspm0 entries same")

same_mspm0(a, b)
