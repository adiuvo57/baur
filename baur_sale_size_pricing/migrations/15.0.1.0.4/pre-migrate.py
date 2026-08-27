# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Fix broken Studio attrs before reloading sale.order form inheritance."""
    replacements = [
        ("['sale', 'done'])]]}", "['sale', 'done'])]}"),
        ("['sale', 'done'])]]", "['sale', 'done'])]"),
        (
            "{'required': [('state', 'in', ['sale', 'done'])]]}",
            "{'required': [('state', 'in', ['sale', 'done'])]}",
        ),
    ]
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
