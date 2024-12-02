import json
from sqlalchemy import String, TypeDecorator


class Json(TypeDecorator):
    impl = String

    cache_ok = True

    def process_bind_param(self, value, dialect):
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        return json.loads(value)
