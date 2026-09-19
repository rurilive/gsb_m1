"""templet 演示：变量、过滤器、for/if、自动转义与 include 公共片段。"""

from templet import Engine, TemplateCycleError

INVOICE = """\
尊敬的 {{ customer.name }}：

  订单 {{ order_id }} 共 {{ items | length }} 项，明细如下：
{% for name, price in items %}  - {{ name }}    ￥{{ price }}
{% endfor %}
{% if total >= 1000 %}  您是本月大额客户，已附赠运费券。
{% else %}  满 1000 元可附赠运费券，还差 ￥{{ short }}。
{% endif %}
  客服备注：{{ remark }}
"""

PAGE = """\
<h1>{{ title }}</h1>
<p>{{ user_input }}</p>
<p>{{ user_input | safe }}</p>
"""

HEADER = """\
<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{{ page_title }}</title></head>
<body>
<header>橘子科技 · {{ channel }}运营页</header>
<main>
"""

FOOTER = """\
</main>
<footer>© 2026 橘子科技 · 收件人 {{ customer.name }}</footer>
</body>
</html>
"""

LAYOUT = """\
{% include "header.html" %}
{% include "content.html" %}
{% include "footer.html" %}
"""

CONTENT = """\
  <h2>{{ page_title }}</h2>
  <p>{{ summary }}</p>
  <ul>
{% for item in features %}    <li>{{ item }}</li>
{% endfor %}  </ul>
"""


def main():
    print("=== 订单邮件（for / if / 过滤器） ===")
    engine = Engine()
    body = engine.render_string(INVOICE, {
        "customer": {"name": "杭州·橘子科技"},
        "order_id": "SO-2042",
        "items": [("前端监控SaaS", 680), ("压测服务", 350)],
        "total": 1030,
        "short": 320,
        "remark": "发票抬头已登记",
    })
    print(body)

    print("=== 自动转义（默认开，safe 关闭） ===")
    print(engine.render_string(PAGE, {
        "title": "用户留言",
        "user_input": '<script>alert("xss")</script>',
    }))

    print("=== include：公共头部/底部，外层变量一路可见 ===")
    for name, source in (("header.html", HEADER),
                         ("footer.html", FOOTER),
                         ("content.html", CONTENT),
                         ("layout.html", LAYOUT)):
        engine.register(name, source)
    page_ctx = {
        "page_title": "双十一压测护航",
        "channel": "邮件",
        "customer": {"name": "运维老王"},
        "summary": "大促前全链路压测，含 HTML 特殊字符 <b>&</b> 默认转义。",
        "features": ["容量评估", "限流预案", "7x24 值班"],
    }
    print(engine.render("layout.html", page_ctx))

    print("=== include 深度超限（直接/间接递归） ===")
    cyclic = Engine(max_include_depth=5)
    cyclic.register("self.html", '{% include "self.html" %}')
    try:
        cyclic.render("self.html")
    except TemplateCycleError as exc:
        print("捕获 TemplateCycleError:", exc)


if __name__ == "__main__":
    main()
