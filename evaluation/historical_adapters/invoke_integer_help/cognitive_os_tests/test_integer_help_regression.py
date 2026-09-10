"""Modern pytest coverage for Invoke's historical integer-help defect."""

from invoke.collection import Collection
from invoke.parser import Context
from invoke.tasks import task


def _parser_context():
    @task
    def sample(context, name="value", intval=5, verbose=False):
        pass

    return Collection(sample).to_contexts()[0]


def test_integer_defaults_render_int_help_placeholder():
    assert Context.help_for(_parser_context(), "--intval") == (
        "-i INT, --intval=INT",
        "",
    )


def test_string_defaults_keep_string_help_placeholder():
    assert Context.help_for(_parser_context(), "--name") == (
        "-n STRING, --name=STRING",
        "",
    )


def test_boolean_flags_remain_placeholder_free():
    assert Context.help_for(_parser_context(), "--verbose") == (
        "-v, --verbose",
        "",
    )
