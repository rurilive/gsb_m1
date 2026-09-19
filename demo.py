"""templet 现状演示：变量、过滤器、for/if 与自动转义。"""

from templet import Engine

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

    # TODO(下个版本): include 节点落地后，在这里演示页面骨架 include
    # 公共片段，以及 include 深度超限时 TemplateCycleError 的报错路径。


if __name__ == "__main__":
    main()
