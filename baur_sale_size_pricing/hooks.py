# -*- coding: utf-8 -*-
"""Repair malformed Studio sale.order form attrs that block view validation."""


def fix_broken_sale_view_attrs(cr):
    """Fix extra ']' typo in attrs on sale.order views.

    Broken:  {'required': [('state', 'in', ['sale', 'done'])]]}
    Correct: {'required': [('state', 'in', ['sale', 'done'])]}
    """
    replacements = [
        ("['sale', 'done'])]]}", "['sale', 'done'])]}"),
        ("['sale', 'done'])]]", "['sale', 'done'])]"),
        (
            "{'required': [('state', 'in', ['sale', 'done'])]]}",
            "{'required': [('state', 'in', ['sale', 'done'])]}",
        ),
    ]
    # Odoo 15 stores view architecture in arch_db; older DBs may still have arch.
    for column in ('arch_db', 'arch'):
        cr.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'ir_ui_view' AND column_name = %s
            """,
            (column,),
        )
        if not cr.fetchone():
            continue
        for bad, good in replacements:
            cr.execute(
                """
                UPDATE ir_ui_view
                   SET {column} = REPLACE({column}, %s, %s)
                 WHERE {column} IS NOT NULL
                   AND {column} LIKE %s
                """.format(column=column),
                (bad, good, '%' + bad + '%'),
            )


def pre_init_hook(cr):
    fix_broken_sale_view_attrs(cr)
