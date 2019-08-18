"""Various methods involving user input."""

import errno


class NoChoice(KeyboardInterrupt):
    """Raised by :obj:`userquery` if no choice was made.

    HACK: this subclasses KeyboardInterrupt, so if you ignore this it
    should do something reasonable.
    """


def userquery(prompt, out, err, responses=None, default_answer=None, limit=3):
    """Ask the user to choose from a set of options.

    Displays a prompt and a set of responses, then waits for a
    response which is checked against the responses. If there is an
    unambiguous match the value is returned.

    If the user does not input a valid response after a number of
    tries :obj:`NoChoice` is raised. You can catch this if you want to do
    something special. Because it subclasses C{KeyboardInterrupt}
    the default behaviour is to abort as if the user hit ctrl+c.

    :type prompt: C{basestring} or a tuple of things to pass to a formatter.
        XXX this is a crummy api but I cannot think of a better one supporting
        the very common case of wanting just a string as prompt.
    :type out: formatter.
    :type err: formatter.
    :type responses: mapping with C{basestring} keys and tuple values.
    :param responses: mapping of user input to function result.
        The first item in the value tuple is returned, the rest is passed to
        out.  Defaults to::
        {'yes': (True, out.fg('green'), 'Yes'),
        'no': (False, out.fg('red'), 'No')}
    :param default_answer: returned if there is no input
        (user just hits enter). Defaults to True if responses is unset,
        unused otherwise.
    :param limit: number of allowed tries.
    """
    if responses is None:
        responses = {
            'yes': (True, out.fg('green'), 'Yes'),
            'no': (False, out.fg('red'), 'No'),
            }
        if default_answer is None:
            default_answer = True
    if default_answer is not None:
        for val in responses.values():
            if val[0] == default_answer:
                default_answer_name = val[1:]
                break
        else:
            raise ValueError('default answer matches no responses')
    for i in range(limit):
        # XXX see docstring about crummyness
        if isinstance(prompt, tuple):
            out.write(autoline=False, *prompt)
        else:
            out.write(prompt, autoline=False)
        out.write(' [', autoline=False)
        prompts = list(responses.values())
        for choice in prompts[:-1]:
            out.write(autoline=False, *choice[1:])
            out.write(out.reset, '/', autoline=False)
        out.write(autoline=False, *prompts[-1][1:])
        out.write(out.reset, ']', autoline=False)
        if default_answer is not None:
            out.write(' (default: ', autoline=False)
            out.write(autoline=False, *default_answer_name)
            out.write(')', autoline=False)
        out.write(': ', autoline=False)
        try:
            response = input()
        except EOFError as e:
            out.write("\nNot answerable: EOF on STDIN")
            raise NoChoice() from e
        except IOError as e:
            if e.errno == errno.EBADF:
                out.write("\nNot answerable: STDIN is either closed, or not readable")
                raise NoChoice() from e
            raise
        if not response:
            return default_answer
        results = sorted(set(
            (key, value) for key, value in responses.items()
            if key[:len(response)].lower() == response.lower()))
        if not results:
            err.write('Sorry, response %r not understood.' % (response,))
        elif len(results) > 1:
            err.write(
                'Response %r is ambiguous (%s)' %
                (response, ', '.join(key for key, val in results)))
        else:
            return list(results)[0][1][0]

    raise NoChoice()
