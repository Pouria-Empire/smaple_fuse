import subprocess
import os
# Mount the remote directory locally
remote_host = '188.40.23.247'
remote_directory = '/root/sshfs'
local_mount_point = './remote'
local_directory = './'

# Check if the file exists locally, if not, mount the remote directory
file_name = 'test.txt'
local_file_path = os.path.join(local_directory, file_name)

if os.path.exists(local_file_path):
    # Read from the local file
    with open(local_file_path, 'r') as file:
        content = file.read()
        print(content)
else:
    # Mount the remote directory
    mount_command = ['sshfs', f'{remote_host}:{remote_directory}', local_mount_point]
    subprocess.run(mount_command, check=True)
    print("Server mounterd")

    # Read from the mounted remote directory
    remote_file_path = os.path.join(local_mount_point, file_name)
    with open(remote_file_path, 'r') as file:
        content = file.read()
        print(content)

    # Unmount the remote directory
    unmount_command = ['fusermount', '-u', local_mount_point]
    subprocess.run(unmount_command, check=True)