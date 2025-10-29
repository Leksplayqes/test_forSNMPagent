import paramiko
import time
import datetime


def fpga_reload():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('192.168.72.72', port=22, username='admin', password='')
    ssh.get_transport()
    for i in range(1, 1000):
        ssh.exec_command(f'fpga-reload 9')
        time.sleep(35)
        stdin, stdout, stderr = ssh.exec_command(f'state slot 9')
        result = stdout.read().decode()
        print(result)
        if 'KS 9 & 10 is equal' not in result:
            print(f"{datetime.datetime.now()} - {i} - False ")
            break
        print(f"{datetime.datetime.now()} - {i} - True ")
    ssh.close()


if __name__ == "__main__":
    fpga_reload()
