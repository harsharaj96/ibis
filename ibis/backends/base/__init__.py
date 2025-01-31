import abc

from ibis.common.exceptions import TranslationError

__all__ = ('BaseBackend',)


class BaseBackend(abc.ABC):
    """
    Base backend class.

    All Ibis backends are expected to subclass this `Backend` class,
    and implement all the required methods.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """
        Name of the backend, for example 'sqlite'.
        """
        pass

    @property
    @abc.abstractmethod
    def kind(self):
        """
        Backend kind. One of:

        sqlalchemy
            Backends using a SQLAlchemy dialect.
        sql
            SQL based backends, not based on a SQLAlchemy dialect.
        pandas
            Backends using pandas to store data and perform computations.
        spark
            Spark based backends.
        """
        pass

    @property
    @abc.abstractmethod
    def builder(self):
        pass

    @property
    @abc.abstractmethod
    def translator(self):
        pass

    @property
    def dialect(self):
        """
        Dialect class of the backend.

        We generate it dynamically to avoid repeating the code for each
        backend.
        """
        # TODO importing dialects inside the function to avoid circular
        # imports. In the future instead of this if statement we probably
        # want to create subclasses for each of the kinds
        # (e.g. `BaseSQLAlchemyBackend`)
        if self.kind == 'sqlalchemy':
            from ibis.backends.base.sql.alchemy import AlchemyDialect

            dialect_class = AlchemyDialect
        elif self.kind in ('sql', 'pandas', 'spark'):
            from ibis.backends.base.sql.compiler import Dialect

            dialect_class = Dialect
        else:
            raise ValueError(
                f'Backend class "{self.kind}" unknown. '
                'Expected one of "sqlalchemy", "sql", '
                '"pandas" or "spark".'
            )

        dialect_class.translator = self.translator
        return dialect_class

    @abc.abstractmethod
    def connect(connection_string, **options):
        """
        Connect to the underlying database and return a client object.
        """
        pass

    def register_options(self):
        """
        If the backend has custom options, register them here.
        They will be prefixed with the name of the backend.
        """
        pass

    def compile(self, expr, params=None):
        """
        Compile the expression.
        """
        context = self.dialect.make_context(params=params)
        builder = self.builder(expr, context=context)
        query_ast = builder.get_result()
        # TODO make all builders return a QueryAST object
        if isinstance(query_ast, list):
            query_ast = query_ast[0]
        compiled = query_ast.compile()
        return compiled

    def verify(self, expr, params=None):
        """
        Verify `expr` is an expression that can be compiled.
        """
        try:
            self.compile(expr, params=params)
            return True
        except TranslationError:
            return False

    def add_operation(self, operation):
        """
        Decorator to add a translation function to the backend for a specific
        operation.

        Operations are defined in `ibis.expr.operations`, and a translation
        function receives the translator object and an expression as
        parameters, and returns a value depending on the backend. For example,
        in SQL backends, a NullLiteral operation could be translated simply
        with the string "NULL".

        Examples
        --------
        >>> @ibis.sqlite.add_operation(ibis.expr.operations.NullLiteral)
        ... def _null_literal(translator, expression):
        ...     return 'NULL'
        """

        def decorator(translation_function):
            self.translator.add_operation(operation, translation_function)

        return decorator
