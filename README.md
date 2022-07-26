# cardreader_pi
Store card numbers read via MIFARE Classic reader in monthly files, dump files to USB stick on button press.
This program relies on GNU/Linux utilities, so it will not work on Windows.

Run this code on a Raspberry Pi. With a USB MIFARE card reader acting as a virtual keyboard plugged in, this program will write out the data read from the scanned card, along with the current date and time, to monthly files in a local directory.

If a USB stick is plugged in to the RPi, when the pushbutton is pressed, this program will mount the USB stick, write out any new or updated cardinfo files from the local file directory, and unmount the USB stick when finished.

Green and red LEDs show ready and busy status respectively. Buzzer will make an unhappy signal upon any errors mounting, writing to, or unmounting the USB stick.

