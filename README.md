HIKVISION NVR TFTP BRICK FIX

Thanks to Scott Lamb for the original code, this is an extension of his work plus a lot of newer updates so it works on Python3.

**INFO:** When your HIK device bricks itself it defaults itself to an emergency state, stop freaking out there is a fix. The only way to fix this is to host a new firmware file to the NVR or camera from your computer.

If you're running MAC or Windows, download Python first and install from their website. https://www.python.org/downloads/
Next download the "hikvision_unbrick.py" python script file above and a stable version of firmware for your NVR or camera before it was bricked. Most likely this will be the same version that is printed on the box it came with or the previous MAJOR version to the firmware that you just used to brick your device. v4.61 is known to brick NVR's.

**IMPORTANT:** Make sure the firmware version your download is SPECIFIC to your region.

**IMPORTANT:** Change your PC or laptop's IP address to 192.0.0.128 now.

Make sure both files are in the same folder
Run Terminal from MAC or coåmmand prompt "as administrator" from Windows.
In Windows run IDLE, open the script you just downloaded and hit F5 or menu RUN > Run Module. You can do the same for MAC but it may ask you to run it in SUDO (elevated privileges).
In MAC start terminal and navigate to the same folder as both of the files, make sure you run the below command with "sudo" otherwise it will fail.
**sudo python3 hikvision_unbrick.py**

At this point a new window will appear and the script is waiting for you to turn on the device that is bricked.
I would suggest that your PC or laptop is plugged directly into the NVR or camera (via a POE switch).

Wait for the file transfer to occur, once the file is uploaded you'll receive a message to say it's complete.

Turn the device off and reboot it. 
Your device is now saved!


**OTHER NOTES BELOW.**

**How to run (IDLE or terminal)**

Save the script as hikvision_unbrick.py
Putdigicap.dav in the same folder
Open in IDLE → press F5 or bash python3 hikvision_unbrick.py --server-ip 192.0.0.128

Admin rights are required to bind the special IP 192.0.0.128.
• Windows – Run IDLE as Administrator
• macOS/Linux – sudo python3 hikvision_unbrick.py …

You’ll see a live progress bar, handshake confirmation, and a clean shutdown on Ctrl-C. No more crashes!
