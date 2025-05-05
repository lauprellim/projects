# This simply gets the PI's MAC address.

import wifi

mac = ':'.join(['{:02X}'.format(byte) for byte in wifi.radio.mac_address])
print("My MAC address:", mac)