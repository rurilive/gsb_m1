"""templet 现状演示：变量、过滤器、for/if、自动转义与 include。"""

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
<div class="header">{{ site_name }} · {{ page_title }}</div>"""

FOOTER = """\
<div class="footer">© 2026 {{ site_name }}（{{ page_title }}）</div>"""

PAGE_SKELETON = """\
{% include "header.html" %}
<main>
  <h1>{{ page_title }}</h1>
  <p>{{ content }}</p>
</main>
{% include "footer.html" %}"""


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

    print("=== include：公共头部/底部，沿用同一上下文 ===")
    page_engine = Engine()
    page_engine.register("header.html", HEADER)
    page_engine.register("footer.html", FOOTER)
    print(page_engine.render_string(PAGE_SKELETON, {
        "site_name": "橘子运营台",
        "page_title": "活动总览",
        "content": "本周 UV 12.3k",
    }))

    print("=== include 深度超限（直接递归）-> TemplateCycleError ===")
    cyclic = Engine(max_include_depth=3)
    cyclic.register("loop.html", '{% include "loop.html" %}')
    try:
        cyclic.render_string('{% include "loop.html" %}')
    except TemplateCycleError as exc:
        print("TemplateCycleError:", exc)


if __name__ == "__main__":
    main()
