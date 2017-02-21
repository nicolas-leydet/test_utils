import inspect
import re
from copy import deepcopy
from itertools import product
from functools import wraps


class TestExpander(object):
    '''
    Decorator that create multiple versions of the same test function
    Depending on the previous decorations of this function
    with CommonArguments, OptionArguments and TestCases.
    Decorator parameters
        :param desc: descrition of the test
        :param tags: optional list of text tags used as nose tags
    '''

    def __init__(self, desc, _tags=None):
        self.desc = desc
        self.tags = _tags or []

    def __call__(self, function):
        additional_arguments = []
        if hasattr(function, 'tc_additional_arguments'):
            additional_arguments = function.tc_additional_arguments
            del function.tc_additional_arguments
        if hasattr(function, 'tc_test_cases'):
            original_test_cases = list(reversed(function.tc_test_cases))
            del function.tc_test_cases
        else:
            original_test_cases = [{'__positionals': []}]

        arg_groups = [original_test_cases] + additional_arguments
        augmented_test_cases = [deepcopy(merge_dicts(*args))
                                for args in product(*arg_groups)]
        _create_functions_from_testcases(
            function,
            augmented_test_cases,
            get_custom_name_func(self.desc),
            get_custom_doc_func(self.desc, len(augmented_test_cases)),
            self.tags)
        return function


def _create_functions_from_testcases(test_function, test_cases,
                                     naming_func, doc_func, tags):
    stack = inspect.stack()
    frame = stack[2]
    frame_locals = frame[0].f_locals
    test_function.__test__ = True

    for index, test_case in enumerate(test_cases):
        name = naming_func(test_function, index, test_case)
        doc = doc_func(test_function, index, test_case)
        frame_locals[name] = _create_function_from_testcase(test_case,
                                                            test_function,
                                                            name, doc, tags)
    test_function.__test__ = False


def _create_function_from_testcase(test_case, test_function, name, doc, tags):
    positionals = tuple(test_case['__positionals'])
    del test_case['__positionals']

    @wraps(test_function)
    def new_function(*arg):
        return test_function(*(arg + positionals), **test_case)

    new_function.__name__ = name
    old_doc = new_function.__doc__
    old_doc = ' ({})'.format(old_doc) if old_doc else ''
    new_function.__doc = doc + old_doc

    for tag in tags:
        setattr(new_function, tag, True)

    return new_function


class CommonArguments(object):
    def __init__(self, **kwargs):
        self.args = kwargs

    def __call__(self, function):
        if not hasattr(function, 'tc_additional_arguments'):
            function.tc_additional_arguments = []
        function.tc_additional_arguments.append([self.args])
        return function


class OptionArguments(object):
    def __init__(self, *alternatives, **kwargs):
        if alternatives:
            self.options = alternatives
        elif len(kwargs) == 1:
            name, values = kwargs.popitem()
            self.options = [{name: value} for value in values]
        else:
            raise ValueError('options accept alternatives (alt) or '
                             'one kwarg containing a list of values')

    def __call__(self, function):
        if not hasattr(function, 'tc_additional_arguments'):
            function.tc_additional_arguments = []
        function.tc_additional_arguments.append(self.options)
        return function


class TestCases(object):
    def __init__(self, *args, **kwargs):
        self.parameters = kwargs
        self.parameters['__positionals'] = list(args)

    def __call__(self, function):
        if not hasattr(function, 'tc_test_cases'):
            function.tc_test_cases = []
        function.tc_test_cases.append(self.parameters)
        return function


def alt(**kwargs):
    return kwargs


def merge_dicts(*dicts):
    result = {}
    for dictionary in dicts:
        result.update(dictionary)
    return result


def get_custom_name_func(description):
    def custom_name(testcase_func, param_num, param):
        prefix = ''
        if not description.startswith('test'):
            prefix = 'test_'
        return "{prefix}{desc}__case_{index:03d}".format(
            prefix=prefix,
            desc=to_safe_name(description),
            index=param_num)

    return custom_name


def get_custom_doc_func(description, nb_testcases):
    def custom_doc(testcase_func, param_num, params):
        return "{desc} ({index:03d}/{nb}) parameters: {params}".format(
                                             desc=description,
                                             index=param_num,
                                             nb=nb_testcases,
                                             params='')

    return custom_doc


def to_safe_name(s):
    return str(re.sub("[^a-zA-Z0-9_]+", "_", s))


tc = TestCases
common = CommonArguments
options = OptionArguments
test = TestExpander


class TestClass(object):
    # generate 3 tests : one for each tc
    # adding the @common 'token' to each test cases
    @test('It should do it correctly')
    @tc('first', 1.2)
    @tc('second', 19)
    @tc('last', 0.23, opt=True)
    @common(token='dh8dwte38ecnr89tnw34rq232enxq3hrn38r7qr3')
    def _(self, subject, val, token, opt=False):
        print(subject, val, token, opt)

    # sharing the test implementation with the next @test
    @test('position in letters')
    @tc('first')
    @tc('second')
    @test('position in digits')
    @tc('1')
    @tc('2')
    def _(self, position):
        print(position)

    # generate 12 tests :
    # 2 (tc) * 2 (action options) * 3 (val options)
    @test('test reply/forward, with val varying from 0 to 2')
    @tc(subject='short')
    @tc(subject='quite a bit longer and not that long')
    @options(action=['reply', 'forward'])
    @options(val=range(3))
    def _(self, subject, val, action='reply'):
        print(subject, val, action)


# also works on simple functions
# options can also define alt (alternatives)
@test('without class')
@tc(subject='test reply/forward')
@options(alt(action='reply'),
         alt(action='forward', recipient='john'))
def _(subject, action, recipient=None):
    print(subject, action, recipient)
