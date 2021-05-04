"""
Adding and subtracting timestamp/date intervals (dealt with in `_timestamp_op`)
is still WIP since Spark SQL support for these tasks is not comprehensive.
The built-in Spark SQL functions `date_add`, `date_sub`, and `add_months` do
not support timestamps, as they set the HH:MM:SS part to zero. The other option
is arithmetic syntax: <timestamp> + INTERVAL <num> <unit>, where unit is
something like MONTHS or DAYS. However, with the arithmetic syntax, <num>
must be a scalar, i.e. can't be a column like t.int_col.

                        supports        supports        preserves
                        scalars         columns         HH:MM:SS
                     _______________________________ _______________
built-in functions  |               |               |               |
like `date_add`     |      YES      |      YES      |       NO      |
                    |_______________|_______________|_______________|
                    |               |               |               |
arithmetic          |      YES      |       NO      |      YES      |
                    |_______________|_______________|_______________|

"""


import math

import ibis
import ibis.backends.base_sqlalchemy.compiler as comp
import ibis.expr.operations as ops
import ibis.expr.rules as rlz
from ibis.backends.base.sql import quote_identifier

from .registry import operation_registry


def build_ast(expr, context=None):
    from ibis.backends.spark import Backend

    if context is None:
        context = Backend().dialect.make_context()
    builder = SparkQueryBuilder(expr, context=context)
    return builder.get_result()


# ----------------------------------------------------------------------
# Select compilation


class SparkUDFNode(ops.ValueOp):
    def output_type(self):
        return rlz.shape_like(self.args, dtype=self.return_type)


class SparkUDAFNode(ops.Reduction):
    def output_type(self):
        return self.return_type.scalar_type()


class SparkSelectBuilder(comp.SelectBuilder):
    @property
    def _select_class(self):
        return SparkSelect


class SparkQueryBuilder(comp.QueryBuilder):
    select_builder = SparkSelectBuilder


class SparkContext(comp.QueryContext):
    def _to_sql(self, expr, ctx):
        if ctx is None:
            ctx = comp.Dialect.make_context()
        builder = SparkQueryBuilder(expr, context=ctx)
        ast = builder.get_result()
        query = ast.queries[0]
        return query.compile()


class SparkExprTranslator(comp.ExprTranslator):
    _registry = operation_registry

    context_class = SparkContext

    def name(self, translated, name, force=True):
        return '{} AS {}'.format(
            translated, quote_identifier(name, force=force)
        )


rewrites = SparkExprTranslator.rewrites


@rewrites(ops.IsInf)
def spark_rewrites_is_inf(expr):
    arg = expr.op().arg
    return (arg == ibis.literal(math.inf)) | (arg == ibis.literal(-math.inf))


class SparkSelect(comp.Select):
    translator = SparkExprTranslator
