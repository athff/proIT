#!/usr/bin/env python
import sys
import os
sys.path.insert(0, 'e:\\proIT')

# Try to compile the tests file
try:
    with open('e:\\proIT\\people\\tests.py', 'r') as f:
        code = f.read()
    compile(code, 'e:\\proIT\\people\\tests.py', 'exec')
    print('SUCCESS: tests.py syntax is valid')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
except Exception as e:
    print(f'ERROR: {e}')

# Try to import the test module
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location('people.tests', 'e:\\proIT\\people\\tests.py')
    print('Module spec created successfully')
except Exception as e:
    print(f'Import error: {e}')