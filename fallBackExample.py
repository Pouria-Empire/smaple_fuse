primary_dir = './'
fallback_dir = './test/'

import os
def read_file(filename):
    primary_path = os.path.join(primary_dir, filename)
    fallback_path = os.path.join(fallback_dir, filename)

    if os.path.exists(primary_path):
        # Read from primary path
        with open(primary_path, 'r') as file:
            content = file.read()
    elif os.path.exists(fallback_path):
        # Read from fallback path
        with open(fallback_path, 'r') as file:
            content = file.read()
    else:
        # File not found in either location
        raise FileNotFoundError(f"File '{filename}' not found.")

    return content

print(read_file('test.txt'))