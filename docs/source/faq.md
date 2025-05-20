# FAQ

## Question #1

### Q1.1 When running `docker_run.sh`, the following warning message may appear:
```
[WARN] it is recommended to use an **X11 session (with .Xauthority support)** when working with the 'dx-all-suite' container.
```

### Q1.2 After a system reboot or session logout, the container failed to restart due to the following issue: `error mounting /tmp/.docker.xauth`.

Example error message:
```
Error response from daemon: failed to create task for container: failed to create shim task: OCI runtime create failed: runc create failed: unable to start container process: error during container init: error mounting "/run/user/1000/.mutter-Xwaylandauth.N9UI62" to rootfs at "/tmp/.docker.xauth": create mountpoint for /tmp/.docker.xauth mount: cannot create subdirectories in "/var/lib/docker/overlay2/00690e188f08ad4bad24fbc8786b00653e76b44f32d9b88b1ae5ed1e2d7654c8/merged/tmp/.docker.xauth": not a directory: unknown: Are you trying to mount a directory onto a file (or vice-versa)? Check if the specified host path exists and is the expected type
Error: failed to start containers: dx-runtime-22.04
```

## Answer #1

The `dx-all-suite` Docker container uses **X11 forwarding** to display GUI windows when running sample applications or example code. For this, it relies on `xauth` to manage authentication.

However, if the user's host environment is not based on **X11 (with .Xauthority)** but instead uses **Xwayland** or similar, the `xauth` data may be lost after a system reboot or session logout. As a result, the authentication file mount between the host and the container may fail, making it impossible to restart or reuse the container.


Therefore, it is recommended to use an **X11 session (with .Xauthority support)** when working with the `dx-all-suite` container.

You can resolve this issue by setting **X11 as the default session**, as described in the instructions above.

### Set X11 as the Default Session

To make X11 the default session (and disable Wayland), modify the GDM configuration file.

#### For GNOME (Ubuntu-based systems):

1. Open the GDM configuration file with root permissions:

   ```bash
   sudo nano /etc/gdm3/custom.conf
Find the following line and uncomment it (remove the #), or add it if it doesn't exist:

```
WaylandEnable=false
```
Save the file and exit (Ctrl+O, Enter, then Ctrl+X in nano).

Restart the GDM service to apply the changes:

```
sudo systemctl restart gdm3
```

After reboot or GDM restart, the system will use the X11 session by default instead of Wayland.
