"""
Derives a human-readable `packet_type` for a decoded GSMTAP packet.

Not a generic "any `*_element`-suffixed key" scan -- that pattern exists at
every nested ASN.1 CHOICE level (an IE inside a message has its own
`<name>_element` marker, same as the message itself), so a blanket scan
would just as happily report a nested IE's name as the packet's type. This
module instead checks an explicit, finite set of known *top-level* LTE RRC
message names (the message-choice fields from TS 36.331's DL-CCCH-Message /
DL-DCCH-Message / UL-CCCH-Message / UL-DCCH-Message / BCCH-DL-SCH-Message /
PCCH-Message definitions), verified against a real 78,221-packet sample
(27 sessions): 0 ambiguous packets (no packet ever matched more than one
entry), and the only packets that matched none were exactly the
gsmtap.type==15 RACH-response ones handled below as a special case.

NAS-layer message type decoding uses the public, stable TS 24.301 Table
9.8.1/9.8.2 codepoints -- lower risk than the RRC CHOICE-nesting problem
above since these are flat integer codes with no structural ambiguity, but
not independently re-verified against a labeled sample the way the RRC list
was. Unrecognized codes fall back to a numeric label rather than "Unknown",
since the NAS message *is* present and typed, just not in this table yet.
"""

# TS 36.331 top-level RRC message names -> packet_type label. Order doesn't
# matter: verified to be non-overlapping against a real sample (see above).
_RRC_TOPLEVEL_MESSAGES = [
    # DL-CCCH-Message
    "rrcConnectionReestablishment",
    "rrcConnectionReestablishmentReject",
    "rrcConnectionReject",
    "rrcConnectionSetup",
    # DL-DCCH-Message
    "csfbParametersResponseCDMA2000",
    "dlInformationTransfer",
    "handoverFromEUTRAPreparationRequest",
    "mobilityFromEUTRACommand",
    "rrcConnectionReconfiguration",
    "rrcConnectionRelease",
    "securityModeCommand",
    "ueCapabilityEnquiry",
    "counterCheck",
    "ueInformationRequest_r9",
    "loggedMeasurementConfiguration_r10",
    "rnReconfiguration_r10",
    # UL-CCCH-Message
    "rrcConnectionReestablishmentRequest",
    "rrcConnectionRequest",
    # UL-DCCH-Message
    "csfbParametersRequestCDMA2000",
    "measurementReport",
    "rrcConnectionReconfigurationComplete",
    "rrcConnectionReestablishmentComplete",
    "rrcConnectionSetupComplete",
    "securityModeComplete",
    "securityModeFailure",
    "ueCapabilityInformation",
    "ulHandoverPreparationTransfer",
    "ulInformationTransfer",
    "counterCheckResponse",
    "ueInformationResponse_r9",
    "proximityIndication_r9",
    "rnReconfigurationComplete_r10",
    # BCCH-DL-SCH-Message
    "systemInformation",
    "systemInformationBlockType1",
    # BCCH-BCH-Message
    "masterInformationBlock",
    # PCCH-Message
    "paging",
]
_RRC_KEY_TO_LABEL = {f"lte_rrc_lte-rrc_{name}_element": name for name in _RRC_TOPLEVEL_MESSAGES}

GSMTAP_TYPE_MAC_RACH_RESPONSE = "15"
PACKET_TYPE_MAC_RACH_RESPONSE = "MacRachResponse"
PACKET_TYPE_UNKNOWN = "Unknown"

# TS 24.301 Table 9.8.1 -- EMM message type codepoints.
_EMM_MESSAGE_TYPES = {
    65: "AttachRequest",
    66: "AttachAccept",
    67: "AttachComplete",
    68: "AttachReject",
    69: "DetachRequest",
    70: "DetachAccept",
    72: "TrackingAreaUpdateRequest",
    73: "TrackingAreaUpdateAccept",
    74: "TrackingAreaUpdateComplete",
    75: "TrackingAreaUpdateReject",
    76: "ExtendedServiceRequest",
    77: "ControlPlaneServiceRequest",
    78: "ServiceReject",
    79: "ServiceAccept",
    80: "GutiReallocationCommand",
    81: "GutiReallocationComplete",
    82: "AuthenticationRequest",
    83: "AuthenticationResponse",
    84: "AuthenticationReject",
    85: "IdentityRequest",
    86: "IdentityResponse",
    92: "AuthenticationFailure",
    93: "SecurityModeCommand",
    94: "SecurityModeComplete",
    95: "SecurityModeReject",
    96: "EmmStatus",
    97: "EmmInformation",
    98: "DownlinkNasTransport",
    99: "UplinkNasTransport",
    100: "CsServiceNotification",
    104: "DownlinkGenericNasTransport",
    105: "UplinkGenericNasTransport",
}

# TS 24.301 Table 9.8.2 -- ESM message type codepoints.
_ESM_MESSAGE_TYPES = {
    193: "ActivateDefaultEpsBearerContextRequest",
    194: "ActivateDefaultEpsBearerContextAccept",
    195: "ActivateDefaultEpsBearerContextReject",
    197: "ActivateDedicatedEpsBearerContextRequest",
    198: "ActivateDedicatedEpsBearerContextAccept",
    199: "ActivateDedicatedEpsBearerContextReject",
    201: "ModifyEpsBearerContextRequest",
    202: "ModifyEpsBearerContextAccept",
    203: "ModifyEpsBearerContextReject",
    205: "DeactivateEpsBearerContextRequest",
    206: "DeactivateEpsBearerContextAccept",
    208: "PdnConnectivityRequest",
    209: "PdnConnectivityReject",
    210: "PdnDisconnectRequest",
    211: "PdnDisconnectReject",
    212: "BearerResourceAllocationRequest",
    213: "BearerResourceAllocationReject",
    214: "BearerResourceModificationRequest",
    215: "BearerResourceModificationReject",
    216: "EsmStatus",
    217: "EsmInformationRequest",
    218: "EsmInformationResponse",
    219: "EsmNotification",
}


def _rrc_packet_type(rrc_layer):
    """rrc_layer is `layers.get("lte_rrc")` -- a dict, a list of dicts, or
    missing entirely. Returns a label or None."""
    if rrc_layer is None:
        return None
    dicts = rrc_layer if isinstance(rrc_layer, list) else [rrc_layer]
    for d in dicts:
        if not isinstance(d, dict):
            continue
        for key, label in _RRC_KEY_TO_LABEL.items():
            if key in d:
                return label
    return None


def _nas_message_code(value):
    """tshark emits NAS message-type values as hex strings ("0x4a"), not
    decimal -- int(value, 0) auto-detects the 0x prefix. Returns None if
    unparseable."""
    try:
        return int(value, 0)
    except (TypeError, ValueError):
        return None


def _nas_packet_type(nas_layer):
    """
    nas_layer is `layers.get("nas-eps")` -- a dict, a list of dicts, or
    missing entirely. Returns a label or None.

    Looks for keys *ending* in `_nas_msg_emm_type`/`_nas_msg_esm_type`
    rather than one exact key: Wireshark's nas-eps dissector doubles its own
    prefix inconsistently across versions (confirmed directly: tshark 4.6.4
    emits "nas-eps_nas-eps_nas_msg_emm_type", tshark 4.0.17 -- the version
    actually shipped in the Docker image -- emits
    "nas-eps_nas_eps_nas_msg_emm_type" for the identical packet). A suffix
    match is robust to that rather than hardcoding one variant.
    """
    if nas_layer is None:
        return None
    dicts = nas_layer if isinstance(nas_layer, list) else [nas_layer]
    for d in dicts:
        if not isinstance(d, dict):
            continue
        for key, value in d.items():
            if key.endswith("_nas_msg_emm_type"):
                code = _nas_message_code(value)
                if code is not None:
                    return _EMM_MESSAGE_TYPES.get(code, f"Nas:Emm{code}")
            elif key.endswith("_nas_msg_esm_type"):
                code = _nas_message_code(value)
                if code is not None:
                    return _ESM_MESSAGE_TYPES.get(code, f"Nas:Esm{code}")
        # A Service Request's "short" NAS encoding has no message-type octet
        # in the usual position at all (TS 24.301 9.9.3.27) -- it's only
        # identifiable by security_header_type's special value 12. Checked
        # after the loop above since a packet with a real msg_emm_type/
        # msg_esm_type always takes priority.
        for key, value in d.items():
            if key.endswith("_security_header_type"):
                code = _nas_message_code(value)
                if code == 12:
                    return "ServiceRequest"
    return None


def derive_packet_type(layers, gsmtap_type):
    """
    layers: the `pkt["layers"]` dict from one `-T ek` data line.
    gsmtap_type: `layers.get("gsmtap", {}).get("gsmtap_gsmtap_type")` (a
    decimal string, e.g. "15"), passed separately since callers already
    need it for other reasons (e.g. timing_advance decoding).

    Checks the RRC top-level message first (the common case, and the one
    verified against real data above), then NAS message type, then the
    gsmtap.type==15 RACH-response special case, then "Unknown".
    """
    label = _rrc_packet_type(layers.get("lte_rrc"))
    if label:
        return label

    label = _nas_packet_type(layers.get("nas-eps"))
    if label:
        return label

    if gsmtap_type == GSMTAP_TYPE_MAC_RACH_RESPONSE:
        return PACKET_TYPE_MAC_RACH_RESPONSE

    return PACKET_TYPE_UNKNOWN
