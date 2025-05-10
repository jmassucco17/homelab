import hashlib
import pathlib
import subprocess

MANAGED_SERVICES = ['dashboard', 'homepage', 'networking', 'monitoring']
PARENT_DIR = pathlib.Path(__file__).parent.parent
DOCKER_BIN = '/usr/bin/docker'
SYSTEMD_DIR = pathlib.Path('/etc/systemd/system')


# Template for
TEMPLATE = """
[Unit]
Description={name} Docker Compose Service
Requires=docker.service
After=docker.service

[Service]
WorkingDirectory={working_dir}
ExecStart={docker_bin} compose up -d
ExecStop={docker_bin} compose down
Restart=always
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
""".lstrip()


def file_hash(path: pathlib.Path) -> str:
    """Compute sha256 hash of file contents"""
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ''


def write_if_changed(path: pathlib.Path, content: str) -> bool:
    """Write contents (and return True) if different than existing file"""
    existing_hash = file_hash(path)
    new_hash = hashlib.sha256(content.encode()).hexdigest()
    if existing_hash == new_hash:
        return False
    print(f'[UPDATE] {path}')
    path.write_text(content)
    return True


def systemctl(cmd: str):
    """Run systemctl command"""
    subprocess.run(['systemctl'] + cmd.split(), check=False)


def is_enabled(service_name: str) -> bool:
    """Check if service is enabled in systemctl"""
    result = subprocess.run(
        ['systemctl', 'is-enabled', service_name], capture_output=True, text=True
    )
    return result.returncode == 0 and result.stdout.strip() == 'enabled'


def is_active(service_name: str) -> bool:
    """Check if service is active in systemctl"""
    result = subprocess.run(
        ['systemctl', 'is-active', service_name], capture_output=True, text=True
    )
    return result.returncode == 0 and result.stdout.strip() == 'active'


def main():
    updated_services: list[str] = []
    disabled_services: list[str] = []
    stopped_services: list[str] = []

    # Go through managed service directories
    for service in MANAGED_SERVICES:
        service_dir = PARENT_DIR / service
        if not service_dir.is_dir():
            raise ValueError(f'Service {service} has no top-level directory')

        # If no docker-compose file, skip directory
        compose_file = service_dir / 'docker-compose.yml'
        if not compose_file.exists():
            raise ValueError(f'Service {service} has no docker-compose.yml')

        # Establish ini file for service
        service_name = f'{service}.service'
        service_path = SYSTEMD_DIR / service_name
        service_content = TEMPLATE.format(
            name=service_dir.name,
            working_dir=service_dir.resolve(),
            docker_bin=DOCKER_BIN,
        )

        # Write the file to service path if updated
        updated = write_if_changed(service_path, service_content)
        if updated:
            updated_services.append(service_name)

        # Check if enabled and started
        if not is_enabled(service_name):
            disabled_services.append(service_name)
        if not is_active(service_name):
            stopped_services.append(service_name)

    # Enable and start all services
    if disabled_services:
        systemctl('enable ' + ' '.join(disabled_services))
    if stopped_services:
        systemctl('start ' + ' '.join(stopped_services))

    # Reload systemd if any services were updated
    if updated_services:
        print('Reloading systemd...')
        systemctl('daemon-reload')
    else:
        print('All services already up to date.')


if __name__ == '__main__':
    main()
