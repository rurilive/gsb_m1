"""jsonflow 演示：把这两天线上碰到的几个数字问题挨个跑一遍。"""

import io

import jsonflow

ARCHIVE = '{"order_id": 1234567890123456789, "amount": 1e2, "floor": -0.0, "ceiling": 0.0}'


def show(title):
    print()
    print("== %s ==" % title)


def main():
    show("归档往返")
    doc = jsonflow.load(io.StringIO(ARCHIVE))
    out = io.StringIO()
    jsonflow.dump(doc, out)
    print("原文件: %s" % ARCHIVE)
    print("写回后: %s" % out.getvalue())

    show("两条写出路径")
    a = jsonflow.loads('{"amount": 1e2}')
    b = jsonflow.loads('{"amount": 100.0}')
    print("dumps(loads(1e2))    = %s" % jsonflow.dumps(a))
    print("dumps(loads(100.0))  = %s" % jsonflow.dumps(b))
    print("两个值判等: %s" % (a["amount"] == b["amount"],))

    show("重复键")
    raw = '{"k": 1, "k": 2}'
    print("loads 读出来: %s" % (jsonflow.loads(raw),))
    print("load  读出来: %s" % (jsonflow.load(io.StringIO(raw)),))

    show("极限指数")
    try:
        doc = jsonflow.load(io.StringIO('{"cap": 1e400}'))
        out = io.StringIO()
        jsonflow.dump(doc, out)
        print("没报错，写回后: %s" % out.getvalue())
    except jsonflow.JsonError as exc:
        print("报错: %s" % exc)

    show("畸形数字")
    for bad in ("1e", "01", "-"):
        try:
            doc = jsonflow.loads(bad)
            print("%r 当成了 %s" % (bad, doc,))
        except jsonflow.JsonError as exc:
            print("%r 报错: %s" % (bad, exc,))


if __name__ == "__main__":
    main()
