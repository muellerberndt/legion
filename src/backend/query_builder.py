from typing import Any, Dict, Union, Type
from sqlalchemy import select, and_, text
from sqlalchemy.sql import Select
from src.models.base import Asset, Project, Base
from src.util.logging import Logger
import json


class QueryBuilder:
    """Safe SQL query builder for assets and projects

    Query Specification Format:
    {
        "from": "assets" | "projects",  # Required: Base table
        "join": {  # Optional: Join specification
            "table": "assets" | "projects",
            "on": {  # Join conditions as field mappings
                "left_field": "right_field"  # e.g. "project_id": "id"
            }
        },
        "select": [  # Optional: Fields to select
            "table.field",  # e.g. "assets.id", "projects.name"
        ],
        "where": [  # Optional: List of conditions
            {
                "field": "table.field",  # e.g. "assets.asset_type"
                "op": "=" | "!=" | ">" | "<" | ">=" | "<=" | "like" | "ilike" | "in" | "not in" | "is null" | "is not null",
                "value": <any>  # Value to compare against
            }
        ],
        "order_by": [  # Optional: List of ordering specifications
            {
                "field": "table.field",  # e.g. "assets.created_at"
                "direction": "asc" | "desc"
            }
        ],
        "limit": <int>,  # Optional: Number of results to return
        "offset": <int>  # Optional: Number of results to skip
    }
    """

    # Define allowed tables and their models
    ALLOWED_TABLES = {"projects": Project, "assets": Asset}

    # Define allowed SQL functions with their exact formats
    ALLOWED_FUNCTIONS = {
        "count(*) as count": "COUNT(*) as count",
        "count(*) as total": "COUNT(*) as total",
        "count(*) as total_projects": "COUNT(*) as total_projects",
        "count(*)": "COUNT(*)",  # Default format without alias
    }

    def __init__(self):
        self.logger = Logger("QueryBuilder")
        self._table = None
        self._joins = []
        self._conditions = []
        self._order_by = []
        self._limit = None
        self._offset = None
        self._selected_fields = set()

    @classmethod
    def from_spec(cls, spec: Dict[str, Any]) -> "QueryBuilder":
        """Create QueryBuilder from specification"""
        builder = cls()
        builder.logger.debug(f"Building query from spec: {spec}")

        # Get table name
        if "from" not in spec:
            raise ValueError("Query specification must include 'from' field")
        table_name = spec["from"]
        builder.logger.debug(f"Using table: {table_name}")

        # Verify table access
        if table_name not in cls.ALLOWED_TABLES:
            raise ValueError(f"Access to table '{table_name}' is not allowed. Allowed tables: {', '.join(cls.ALLOWED_TABLES)}")

        # Set table
        builder.from_table(table_name)

        # Add join if specified
        if "join" in spec:
            if not isinstance(spec["join"], dict):
                raise ValueError("'join' must be a dictionary")
            if "table" not in spec["join"] or "on" not in spec["join"]:
                raise ValueError("Join specification must include 'table' and 'on' fields")
            builder.logger.debug(f"Adding join: {spec['join']}")
            builder.join(spec["join"]["table"], spec["join"]["on"])

        # Add select fields
        if "select" in spec:
            if not isinstance(spec["select"], list):
                raise ValueError("'select' must be a list of fields")
            builder.logger.debug(f"Adding select fields: {spec['select']}")
            builder.select(*spec["select"])

        # Add where conditions
        if "where" in spec:
            if not isinstance(spec["where"], list):
                raise ValueError("'where' must be a list of conditions")
            builder.logger.debug(f"Adding where conditions: {spec['where']}")
            for condition in spec["where"]:
                if not isinstance(condition, dict):
                    raise ValueError(f"Invalid where condition: {condition}")
                if "field" not in condition or "op" not in condition:
                    raise ValueError(f"Missing field or operator in condition: {condition}")

                field = condition["field"]
                op = condition["op"]
                value = condition.get("value")

                builder.where(field, op, value)

        # Add order by
        if "order_by" in spec:
            builder.logger.debug(f"Adding order by: {spec['order_by']}")
            if not isinstance(spec["order_by"], list):
                raise ValueError("'order_by' must be a list of sort specifications")
            for order in spec["order_by"]:
                if not isinstance(order, dict):
                    raise ValueError(f"Invalid order by specification: {order}")
                if "field" not in order:
                    raise ValueError("Each order_by spec must include 'field'")
                field = order["field"]
                direction = order.get("direction", "asc")
                builder.order_by(field, direction)

        # Add limit
        if "limit" in spec:
            builder.logger.debug(f"Setting limit: {spec['limit']}")
            builder.limit(spec["limit"])

        # Add offset
        if "offset" in spec:
            builder.logger.debug(f"Setting offset: {spec['offset']}")
            builder.offset(spec["offset"])

        return builder

    @classmethod
    def example_spec(cls) -> Dict:
        """Return an example query specification"""
        return {
            "from": "assets",
            "join": {"table": "projects", "on": {"project_id": "id"}},
            "select": ["assets.id", "assets.source_url", "projects.name"],
            "where": [
                {"field": "assets.asset_type", "op": "=", "value": "github_file"},
                {"field": "projects.platform", "op": "=", "value": "github"},
                {"field": "assets.source_url", "op": "like", "value": "github.com"},
            ],
            "order_by": [{"field": "assets.created_at", "direction": "desc"}],
            "limit": 10,
        }

    def _get_model_for_table(self, table_name: str) -> Type[Base]:
        """Get the SQLAlchemy model for a table name"""
        table_name = table_name.lower()
        if table_name not in self.ALLOWED_TABLES and not table_name.startswith("information_schema."):
            raise ValueError(
                f"Access to table '{table_name}' is not allowed. Allowed tables: {', '.join(self.ALLOWED_TABLES)}"
            )

        if table_name.startswith("information_schema."):
            return text(table_name)  # Return raw text for information_schema queries

        return self.ALLOWED_TABLES[table_name]

    def from_table(self, table: Union[str, Type[Base]]) -> "QueryBuilder":
        """Set the base table for the query"""
        if isinstance(table, str):
            self._table = self._get_model_for_table(table)
        else:
            if table not in self.ALLOWED_TABLES.values():
                raise ValueError(f"Invalid table model: {table}")
            self._table = table
        return self

    def join(self, table_name: str, on: Dict[str, str]) -> "QueryBuilder":
        """Add a JOIN clause

        Args:
            table_name: Name of table to join with
            on: Dictionary of join conditions, e.g. {"project_id": "id"} for assets.project_id = projects.id
        """
        if not self._table:
            raise ValueError("No base table selected. Call from_table() first.")

        # Get the join table model
        join_table = self._get_model_for_table(table_name)

        # Build join condition
        join_conditions = []
        for left_field, right_field in on.items():
            left_col = getattr(self._table, left_field, None)
            right_col = getattr(join_table, right_field, None)
            if not left_col or not right_col:
                raise ValueError(f"Invalid join fields: {left_field}, {right_field}")
            join_conditions.append(left_col == right_col)

        self._joins.append((join_table, join_conditions[0] if len(join_conditions) == 1 else and_(*join_conditions)))
        return self

    def select(self, *fields: str) -> "QueryBuilder":
        """Add fields to SELECT clause"""
        if not self._table:
            raise ValueError("No table selected. Call from_table() first.")

        for field in fields:
            field = field.lower().strip()

            # Check if it's an allowed SQL function
            if any(field.startswith(func.lower()) for func in self.ALLOWED_FUNCTIONS):
                # Find the matching function format
                for allowed_func, safe_format in self.ALLOWED_FUNCTIONS.items():
                    if field.lower() == allowed_func.lower():
                        self._selected_fields.add(text(safe_format))
                        break
                continue

            # Handle normal fields (existing code)
            if "." not in field:
                base_table_name = self._table.__tablename__
                qualified_field = f"{base_table_name}.{field}"
                field = qualified_field

            try:
                table_name, field_name = field.split(".")
            except ValueError:
                raise ValueError(f"Invalid field format: {field}. Use format 'table.field' or just 'field' for base table")

            table = self._get_model_for_table(table_name)
            if not hasattr(table, field_name):
                raise ValueError(f"Field {field_name} does not exist in {table.__name__}")

            field_obj = getattr(table, field_name)
            self._selected_fields.add(field_obj)

        return self

    def where(self, field: str, operator: str, value: Any) -> "QueryBuilder":
        """Add a WHERE condition"""
        if not self._table:
            raise ValueError("No table selected. Call from_table() first.")

        # If field doesn't contain a dot, assume it's from the base table
        if "." not in field:
            base_table_name = self._table.__tablename__
            qualified_field = f"{base_table_name}.{field}"
            self.logger.debug(f"Qualifying field {field} as {qualified_field}")
            field = qualified_field

        try:
            table_name, field_name = field.split(".")
        except ValueError:
            raise ValueError(f"Invalid field format: {field}. Use format 'table.field' or just 'field' for base table")

        # Get the table model
        table = self._get_model_for_table(table_name)

        # Verify field exists
        if not hasattr(table, field_name):
            raise ValueError(f"Field {field_name} does not exist in {table.__name__}")

        field_obj = getattr(table, field_name)

        allowed_operators = {
            "=": lambda f, v: f == v,
            "!=": lambda f, v: f != v,
            ">": lambda f, v: f > v,
            "<": lambda f, v: f < v,
            ">=": lambda f, v: f >= v,
            "<=": lambda f, v: f <= v,
            "like": lambda f, v: f.like(f"%{v}%"),
            "ilike": lambda f, v: f.ilike(f"%{v}%"),
            "in": lambda f, v: f.in_(v if isinstance(v, (list, tuple)) else [v]),
            "not in": lambda f, v: ~f.in_(v if isinstance(v, (list, tuple)) else [v]),
            "is null": lambda f, _: f.is_(None),
            "is not null": lambda f, _: f.isnot(None),
            "?": lambda f, v: text(f"{f.key} ? :value").bindparams(value=v),
            "?*": lambda f, v: text(
                f"EXISTS (SELECT 1 FROM json_array_elements_text({f.key}::json) as elem WHERE lower(elem) = lower(:value))"
            ).bindparams(value=v),
            "@>": lambda f, v: text(f"CAST({f.key} AS jsonb) @> CAST(:value AS jsonb)").bindparams(value=json.dumps(v)),
        }

        if operator not in allowed_operators:
            raise ValueError(f"Invalid operator: {operator}. Allowed operators: {', '.join(allowed_operators.keys())}")

        condition = allowed_operators[operator](field_obj, value)
        self._conditions.append(condition)

        return self

    def order_by(self, field: str, direction: str = "asc") -> "QueryBuilder":
        """Add an ORDER BY clause"""
        if not self._table:
            raise ValueError("No table selected. Call from_table() first.")

        direction = direction.lower()
        if direction not in ("asc", "desc"):
            raise ValueError(f"Invalid sort direction: {direction}")

        # Check if field is a whitelisted function
        if field.lower() in self.ALLOWED_FUNCTIONS:
            # Use raw SQL for allowed functions
            order_clause = text(f"{self.ALLOWED_FUNCTIONS[field.lower()]} {direction}")
            self._order_by.append(order_clause)
            return self

        # If field doesn't contain a dot, assume it's from the base table
        if "." not in field:
            base_table_name = self._table.__tablename__
            qualified_field = f"{base_table_name}.{field}"
            self.logger.debug(f"Qualifying field {field} as {qualified_field}")
            field = qualified_field

        try:
            table_name, field_name = field.split(".")
        except ValueError:
            raise ValueError(f"Invalid field format: {field}. Use format 'table.field' or just 'field' for base table")

        table = self._get_model_for_table(table_name)
        if not hasattr(table, field_name):
            raise ValueError(f"Field {field_name} does not exist in {table.__name__}")

        field_obj = getattr(table, field_name)
        self._order_by.append(field_obj.asc() if direction == "asc" else field_obj.desc())

        return self

    def limit(self, limit: int) -> "QueryBuilder":
        """Add LIMIT clause"""
        if not isinstance(limit, int) or limit < 0:
            raise ValueError("Limit must be a positive integer")
        self._limit = limit
        return self

    def offset(self, offset: int) -> "QueryBuilder":
        """Add OFFSET clause"""
        if not isinstance(offset, int) or offset < 0:
            raise ValueError("Offset must be a positive integer")
        self._offset = offset
        return self

    def build(self) -> Select:
        """Build and return the SQLAlchemy query"""
        if not self._table:
            raise ValueError("No table selected. Call from_table() first.")

        # Start with base query
        if self._selected_fields:
            query = select(*self._selected_fields)
        else:
            query = select(self._table)

        # Add JOINs
        for join_table, join_condition in self._joins:
            query = query.join(join_table, join_condition)

        # Add WHERE conditions
        if self._conditions:
            query = query.where(and_(*self._conditions))

        # Add ORDER BY
        if self._order_by:
            query = query.order_by(*self._order_by)

        # Add LIMIT and OFFSET
        if self._limit is not None:
            query = query.limit(self._limit)
        if self._offset is not None:
            query = query.offset(self._offset)

        self.logger.debug(f"Built query: {query}")
        return query

    def __str__(self) -> str:
        """Return the SQL string representation of the query"""
        return str(self.build().compile(compile_kwargs={"literal_binds": True}))

    @classmethod
    def example(cls) -> str:
        """Return example usage of the query builder"""
        return """
        # Example usage:
        query = (QueryBuilder()
            .from_table("assets")
            .join("projects", {"assets.project_id": "projects.id"})
            .select("assets.id", "assets.identifier", "assets.source_url", "projects.name")
            .where("projects.project_source", "=", "immunefi")
            .where("assets.asset_type", "=", "github_file")
            .order_by("assets.created_at", "desc")
            .limit(10)
            .build()
        )

        # Another example with more complex conditions:
        query = (QueryBuilder()
            .from_table("projects")
            .join("assets", {"id": "project_id"})
            .select("projects.name", "projects.description", "assets.identifier")
            .where("projects.project_type", "=", "bounty")
            .where("assets.asset_type", "=", "deployed_contract")
            .where("projects.keywords", "?*", "defi")
            .order_by("projects.created_at", "desc")
            .build()
        )
        """

    def where_raw(self, condition: str) -> "QueryBuilder":
        """Add a raw SQL WHERE condition"""
        self._conditions.append(text(condition))
        return self

    def order_by_raw(self, clause: str) -> "QueryBuilder":
        """Add a raw SQL ORDER BY clause"""
        self._order_by.append(text(clause))
        return self
