import re
from marshmallow import Schema, fields, ValidationError, validate

from .others import str2bool
from .pytimeparse import timeparse


# deprecated
def get_valid_interval(s):
    pattern = re.compile(r'^\d+[m|h|d]$')
    if pattern.match(s):
        return s
    else:
        raise ValidationError(f"Invalid interval format '^\\d+[m|h|d]$' for {s}")


class FiledScheduleInterval(fields.Field):
    """Field that serializes to a string of numbers and deserializes
    to a list of numbers.
    """

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return ""
        return str(value)

    def _deserialize(self, value, attr, data, **kwargs):
        seconds = timeparse(value)
        if seconds is None:
            raise ValidationError("Invalid interval format, refer to https://github.com/wroberts/pytimeparse!")
        else:
            return value


class FiledMyList(fields.Field):
    """Field that serializes to a string of numbers and deserializes
    to a list of numbers.
    """

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return ""
        elif isinstance(value, list) and len(value) == 0:
            return ""
        if isinstance(value, list) and len(value) > 0:
            return ','.join(value)

    def _deserialize(self, value, attr, data, **kwargs):
        try:
            value = list(filter(None, value.split(",")))
            return value
        except ValueError as error:
            raise ValidationError(f"{error}")


class FiledBooleanStr(fields.Field):
    """Field that serializes to a string of numbers and deserializes
    to a list of numbers.
    """

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return "false"
        return str(value).lower()

    def _deserialize(self, value, attr, data, **kwargs):
        try:
            value = str2bool(value)
            return value
        except ValueError as error:
            raise ValidationError(f"{error}")


class FolderBaseSchema(Schema):
    folder = fields.Str(validate=validate.Length(min=1, error='Field cannot be blank'), required=True)


class MonitoredFolderDataSchema(FolderBaseSchema):
    enabled = FiledBooleanStr()
    interval = FiledScheduleInterval()
    offset = fields.Float()
    blacklist = FiledMyList()
    mtime_update_strategy = fields.Str(validate=validate.Length(min=1, error='Field cannot be blank'), required=True)
    # overwrite_db = FiledBooleanStr()


class EditMonitoredFolderDataSchema(MonitoredFolderDataSchema):
    new_folder = fields.Str(validate=validate.Length(min=1, error='Field cannot be blank'), required=True)


class MtimeUpdateStrategySchema(FolderBaseSchema):
    mtime_update_strategy = fields.Str(validate=validate.Length(min=1, error='Field cannot be blank'), required=True)


class EditMonitoredFolderStatusSchema(FolderBaseSchema):
    enabled = FiledBooleanStr()
