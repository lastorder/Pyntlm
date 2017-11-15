# -*- coding: utf-8 -*-

# this code is copy form https://github.com/genotrance/px/blob/master/px.py
import sys

# Default to winkerberos for SSPI
# Try pywin32 SSPI if winkerberos missing
# - pywin32 known to fail in Python 3.6+ : https://github.com/genotrance/px/issues/9
try:
    import winkerberos
except:
    if sys.version_info[0] > 2:
        if sys.version_info[1] > 5:
            print("Requires Python module winkerberos")
            sys.exit()

    # Less than 3.6, can use pywin32
    try:
        import os
        import base64
        import pywintypes
        import sspi
    except:
        print("Requires Python module pywin32 or winkerberos")
        sys.exit()

class NtlmMessageGenerator:
    def __init__(self):
        if "winkerberos" in sys.modules:
            status, self.ctx = winkerberos.authGSSClientInit("NTLM", gssflags=0, mech_oid=winkerberos.GSS_MECH_OID_SPNEGO)
            self.get_response = self.get_response_wkb
        else:
            self.sspi_client = sspi.ClientAuth("NTLM", os.environ.get("USERNAME"), scflags=0)
            self.get_response = self.get_response_sspi

    def get_response_sspi(self, challenge=""):
        challenge = base64.decodebytes(challenge.encode("utf-8"))
        error_msg, output_buffer = self.sspi_client.authorize(challenge)
        response_msg = output_buffer[0].Buffer
        response_msg = base64.encodebytes(response_msg)
        response_msg = response_msg.decode("utf-8").replace('\012', '')
        return response_msg

    def get_response_wkb(self, challenge=""):
        status = winkerberos.authGSSClientStep(self.ctx, challenge)
        auth_req = winkerberos.authGSSClientResponse(self.ctx)
        return auth_req

        