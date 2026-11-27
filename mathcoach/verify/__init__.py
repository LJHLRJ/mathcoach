"""符号验证层：严格 AST 白名单，绝不 eval 原始输入。

入口：``symbolic.are_equivalent`` 判等价，``validate_expression`` 做语法检查。
只比较表达式，不判断题目对错、不读写数据库、不调用模型；确认不了就返回
``UNVERIFIED``，由上层标注“需人工核对”。
"""
