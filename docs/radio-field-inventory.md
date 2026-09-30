# Radio field inventory (candidate wide-table columns)

Generated from `tshark` dissection of real PCAPs produced by `tools/qmdl2pcap`,
against samples of real monitoring sessions across 14 sensors/regions (sample size
varied 90-97 sessions across refinement passes). Values shown are **aggregate
statistics only** -- no real captured field values are included in this document,
since several fields carry real subscriber data (IMSI/TMSI, GPS, phone numbers,
SMS content, assigned IPs).

## Methodology

1. `tshark -T ek` dissection flattened to one row per (field, packet).
2. Decoder-internal noise excluded (ASN.1 PER bookkeeping, array-index labels,
   reserved/"spare" capability bits).
3. **NAS field paths merged**: a NAS-EPS field appears either as a standalone
   `nas-eps` GSMTAP layer or nested inside `lte_rrc`'s `dedicatedInfoNAS` container,
   depending on which diag log entry captured it. Verified empirically (220 fields
   checked directly) that both paths are driven by the same Wireshark NAS-EPS
   dissector and carry the same value semantics -- merged into single columns.
4. Release-version IE variants (e.g. `threshX_Low` / `_r12` / `_r15`) are kept as
   **separate dedicated columns** -- different protocol releases, not coalesced.
5. Column selection is **not** purely cardinality-based. A field being constant
   across a sample is not sufficient reason to exclude it: the project's purpose is
   outlier/anomaly detection, so a field that's fixed almost everywhere except one
   deviating tower is exactly the signal of interest, not noise. Concretely observed:
   `cellBarred` was constant (`1`) across one 90-session sample, but showed 2 rare
   deviations (`0`) out of 73,342 observations in an earlier, different 11-session
   sample -- the signal existed but depended on which sessions were sampled.
6. Given (5), `cellBarred` and `cellReservedForOperatorUse` are included regardless
   of their cardinality bucket in any given sample.

**Column sources:**
- **auto**: medium/high cardinality (6+ distinct values in the sample) -- clearly varying
- **curated low-tier**: low-cardinality (2-5 values) fields matching known
  IMSI-catcher / anomaly categories (neighbor-cell sparsity, reselection steering,
  connection timer profile, measurement-reporting config)
- **manual whitelist**: cause/algorithm/redirect/barring fields that are inherently
  small-enum by protocol design, or specifically flagged regardless of cardinality

**Total candidate columns: 270** (+ ~8-9 pipeline columns: sensor, session,
qmdl timestamp, gps timestamp, latitude, longitude -- two separate float columns,
not a combined point/geometry field -- message-type discriminator, raw_fields
overflow, id)

## Resolved: scope of the outlier-detection principle

Per point 5, the outlier-detection principle justified pulling `cellBarred` and
`cellReservedForOperatorUse` in regardless of cardinality, but does **not** extend to
the rest of the "constant" bucket (700+ fields depending on sample). Decision: ~270
dedicated columns is already a healthy, query-friendly size; the remaining constant-
bucket fields fall through to the `raw_fields` JSON overflow alongside everything else
not promoted to a real column, same as any other field that hasn't earned one yet --
not lost, just not first-class. A field can still be promoted later via migration if
it turns out to matter.

## Still open

- `cellBarred`/`cellReservedForOperatorUse`'s actual 3GPP enum meaning (which value
  means "barred") not yet verified against spec/dissector source -- included
  regardless per the decision above, but worth knowing for interpretation.
- "Other RRC/NAS configuration" is a keyword-categorizer catch-all and hasn't had a
  field-by-field security-relevance pass; included in full per instruction, but a
  closer read would still be useful context for whoever builds queries against it.

## Timing advance -- not in the 270, handled separately

Timing advance does not come through `tshark`'s normal field dissection (GSMTAP type-15
`LteMacFramed` frames show as opaque `data` bytes -- `tshark` doesn't dispatch this
GSMTAP type to its `mac-lte` dissector). It needs a small custom unpack step in our own
pipeline instead of a tshark field extraction. Verified reliable before committing to
this approach:

- Decoded the exact byte layout from `lib/src/gsmtap/mac.rs` (`Header` 3B + payload tag
  1B + `ETRAPIDSubheader` 1B + `RACHResponse`'s bit-packed `tac`(11b)/`ul_grant`(20b)/
  `tc_rnti`(16b), 6B) against 27 real sessions, 2298 packets total.
- **0 decode failures**, **0% sentinel/invalid values** (Qualcomm's `0xFFFF` "RAR
  received but TA not valid" marker, which the current code doesn't check for before
  masking -- becomes exactly `2047` after the `& 0x7FF` mask, worth excluding
  defensively in our own parser even though it didn't appear in this sample).
- Value distribution is physically plausible: heavily concentrated at 0-9 (close-range,
  as expected for most UEs), tapering to a max of 134 -- well within valid LTE TA range.

Implication for the future radio pipeline: timing advance needs its own small decode
function (not a `tshark` field name), separate from the 270 columns below.

## Deferred: signal strength (RSRP/RSRQ/RSSI via GSMTAP type-17)

Investigated and deliberately deferred, noted here so it isn't forgotten later.

Unlike timing advance, signal strength genuinely does not reach our PCAPs today --
not a parsing gap on our side, a gap in Rayhunter's `lib` crate itself:

- The raw diag log (`0xb17f`, `LOG_LTE_ML1_SERVING_CELL_MEAS_AND_EVAL_C`) *is* enabled
  and captured on currently-deployed sensors (`lib/src/diag_device.rs`).
- The diag-layer parser *can* decode the raw bytes into RSRP/RSRQ/RSSI (there's even a
  unit test exercising it, in `lib/src/diag/diaglog/ml1.rs`).
- But the GSMTAP-conversion step (`log_to_gsmtap()` in `lib/src/gsmtap/parser.rs`) has
  no match arm for this log type -- it falls through to "ignoring unhandled log type"
  and is silently dropped. The data is captured on-device but never makes it past
  Rayhunter's own `lib` crate.

A fix exists already: PR #1061 ("Signal strength and timing advance capture", closed
unmerged) on `South-Lighthouse/rayhunter`, branch `gsm-timing-advance`, adds the missing
match arm (~10 lines) plus RSRP decoding. That branch is 86 commits behind current
`lib`'s structure though (predates the `gsmtap/` module reorganization), so it can't be
used as-is -- the fix would need to be re-applied against the current module layout.

If this becomes worth pursuing later: port just the `log_to_gsmtap()` match arm and the
`LteMl1ServingCellMeasPacket` RSRP-decoding helpers from that PR's diff onto current
`lib`, add a GSMTAP type-17 write path in `lib/src/pcap.rs` (or reuse an existing type),
and extend `tools/qmdl2pcap` accordingly.

## Candidate columns by category

### Other RRC/NAS configuration (156)

| field | source | cardinality | distinct values |
|---|---|---|---|
| `c1` | auto | medium | 10 |
| `pagingRecordList` | auto | medium | 15 |
| `si_Periodicity` | auto | medium | 6 |
| `SIB_Type` | auto | medium | 8 |
| `sib_TypeAndInfo_item` | auto | medium | 8 |
| `schedulingInfoList` | auto | medium | 6 |
| `systemInfoValueTag` | auto | medium | 32 |
| `lateNonCriticalExtension` | auto | medium | 39 |
| `rrc_rrc_radioFrequencyBandEUTRA` | auto | medium | 10 |
| `cyclicShift` | auto | medium | 8 |
| `rootSequenceIndex` | auto | high | 200+ |
| `pusch_HoppingOffset` | auto | medium | 8 |
| `prach_ConfigIndex` | auto | medium | 10 |
| `prach_FreqOffset` | auto | medium | 14 |
| `zeroCorrelationZoneConfig` | auto | medium | 10 |
| `referenceSignalPower` | auto | medium | 24 |
| `n1PUCCH_AN` | auto | medium | 20 |
| `nRB_CQI` | auto | medium | 19 |
| `preambleInitialReceivedTargetPower` | auto | medium | 13 |
| `numberOfRA_Preambles` | auto | medium | 9 |
| `p0_NominalPUSCH` | auto | medium | 10 |
| `p0_NominalPUCCH` | auto | medium | 11 |
| `hysteresis` | auto | medium | 7 |
| `threshServingLow` | auto | medium | 7 |
| `sizeOfRA_PreamblesGroupA` | auto | medium | 6 |
| `ARFCN_ValueGERAN` | auto | high | 85 |
| `measResultListEUTRA` | auto | medium | 8 |
| `t_Reordering` | auto | medium | 7 |
| `t_StatusProhibit` | auto | medium | 6 |
| `t_PollRetransmit` | auto | medium | 9 |
| `cellIndex` | auto | medium | 32 |
| `nas.gsm_a_gsm_a_L3_protocol_discriminator` | auto | medium | 16 |
| `q_OffsetCell` | auto | medium | 24 |
| `cellIndividualOffset` | auto | medium | 17 |
| `srs_SubframeConfig` | auto | medium | 8 |
| `priority` | auto | medium | 10 |
| `nomPDSCH_RS_EPRE_Offset` | auto | medium | 8 |
| `start` | auto | high | 200+ |
| `nas.emm_nas_key_set_id` | auto | medium | 8 |
| `cqi_pmi_ConfigIndex` | auto | high | 126 |
| `ri_ConfigIndex` | auto | medium | 7 |
| `a3_Offset` | auto | medium | 9 |
| `nas.seq_no_short` | auto | medium | 32 |
| `nas.emm_short_mac` | auto | high | 200+ |
| `cqi_PUCCH_ResourceIndex` | auto | high | 56 |
| `nas.gsm_a_gsm_a_len` | auto | high | 77 |
| `maxHARQ_Tx` | auto | medium | 6 |
| `q_OffsetFreq` | auto | medium | 24 |
| `p_a` | auto | medium | 7 |
| `dedicatedInfoNAS` | auto | high | 200+ |
| `cellsToAddModList` | auto | medium | 30 |
| `sr_SubframeOffset` | auto | medium | 40 |
| `sr_PUCCH_ResourceIndex` | auto | high | 96 |
| `sr_ConfigIndex` | auto | high | 73 |
| `nas.gsm_a_gm_gsm_a_gm_sm_pco_length` | auto | medium | 11 |
| `nas.gsm_a_gm_gsm_a_gm_sm_pco_pid` | auto | medium | 11 |
| `data.data_data_data` | auto | high | 200+ |
| `betaOffset_RI_Index` | auto | medium | 6 |
| `ueCapabilityRAT_Container` | auto | medium | 32 |
| `rrc_rrc_start_CS` | auto | medium | 13 |
| `rrc_rrc_start_PS` | auto | medium | 10 |
| `sf40` | auto | medium | 40 |
| `freqPriorityListEUTRA` | auto | medium | 6 |
| `bandEUTRA` | auto | medium | 14 |
| `nas.gsm_a_gm_gsm_a_gm_elem_id` | auto | medium | 14 |
| `nas.gsm_a_gsm_a_common_elem_id` | auto | medium | 8 |
| `nas.spare_bits` | auto | medium | 6 |
| `nas.nas_msg_emm_type` | auto | medium | 24 |
| `numberOfPreamblesSent_r16` | auto | medium | 8 |
| `sf320` | auto | high | 200+ |
| `nas.msg_auth_code` | auto | high | 200+ |
| `nas.seq_no` | auto | high | 200+ |
| `n4TxAntenna_tm4` | auto | medium | 6 |
| `interFreqExcludedCellList` | auto | medium | 16 |
| `gp0` | auto | medium | 40 |
| `hyperSFN_r13` | auto | high | 200+ |
| `freqPriorityListUTRA_FDD` | auto | medium | 6 |
| `nas.emm_elem_id` | auto | medium | 9 |
| `explicitListOfARFCNs` | auto | medium | 6 |
| `startingARFCN` | auto | medium | 20 |
| `nas.bearer_id` | auto | medium | 16 |
| `nas.esm_proc_trans_id` | auto | high | 172 |
| `gp1` | auto | high | 75 |
| `nas.nas_msg_esm_type` | auto | medium | 17 |
| `srs_ConfigIndex` | auto | medium | 40 |
| `freqDomainPosition` | auto | medium | 11 |
| `cqi_PUCCH_ResourceIndex_r10` | auto | medium | 33 |
| `nextHopChainingCount` | auto | medium | 7 |
| `ra_PreambleIndex` | auto | medium | 21 |
| `nas.gsm_a_dtap_gsm_a_dtap_elem_id` | auto | medium | 7 |
| `nas.ipcp.ipcp_ipcp_opt_pri_dns_address` | auto | medium | 8 |
| `nas.ipcp.ipcp_opt_pri_dns` | auto | medium | 8 |
| `nas.ipcp.ipcp_opt_sec_dns` | auto | medium | 7 |
| `nas.ipcp.ipcp_ipcp_opt_sec_dns_address` | auto | medium | 7 |
| `nas.emm_tai_tac` | auto | medium | 40 |
| `nas.emm_esm_msg_cont` | auto | high | 200+ |
| `nas.emm_mme_code` | auto | medium | 24 |
| `nas.emm_mme_grp_id` | auto | medium | 15 |
| `nas.gsm_a_gsm_a_lac` | auto | medium | 33 |
| `nas.gsm_a_dtap_gsm_a_dtap_emergency_bcd_num` | auto | medium | 17 |
| `intraFreqExcludedCellList` | auto | medium | 15 |
| `randomValue` | auto | high | 200+ |
| `nas.emm_res` | auto | high | 200+ |
| `nas.gsm_a_dtap_gsm_a_dtap_rand` | auto | high | 200+ |
| `nas.gsm_a_dtap_gsm_a_dtap_autn` | auto | high | 200+ |
| `nas.gsm_a_dtap_gsm_a_dtap_autn_mac` | auto | high | 200+ |
| `nas.gsm_a_dtap_gsm_a_dtap_autn_sqn_xor_ak` | auto | high | 200+ |
| `nas.chap.chap_chap_value` | auto | high | 126 |
| `nas.gsm_a_gm_gsm_a_gm_sm_apn` | auto | medium | 18 |
| `cellsToAddModListUTRA_FDD` | auto | medium | 19 |
| `mmegi` | auto | medium | 14 |
| `nas.emm_nas_msg_cont` | auto | high | 66 |
| `nas.gsm_a_dtap.gsm_a_dtap_gsm_a_dtap_tio` | auto | medium | 7 |
| `nas.gsm_a_rp.gsm_a_gsm_a_len` | auto | medium | 31 |
| `nr-rrc_nr-rrc_bandEUTRA` | auto | medium | 8 |
| `nas.gsm_a_dtap.gsm_a_gsm_a_skip_ind` | auto | medium | 16 |
| `nas.gsm_a_dtap.gsm_a_dtap_gsm_a_dtap_msg_tp_type` | auto | high | 114 |
| `nas.esm_apn_ambr_dl_ext` | auto | medium | 7 |
| `nas.esm_apn_ambr_dl_total` | auto | medium | 7 |
| `nas.gsm_a_dtap_gsm_a_dtap_number_of_spare_bits` | auto | medium | 6 |
| `nr-rrc_nr-rrc_bandNR` | auto | medium | 7 |
| `nas.gsm_a_dtap_gsm_a_dtap_text_string` | auto | medium | 7 |
| `nas.gsm_a_gm_gsm_a_gm_sm_pco_dns_ipv4` | auto | medium | 9 |
| `nas.gsm_a_dtap.gsm_a_gsm_a_len` | auto | medium | 31 |
| `nas.gsm_a_rp.gsm_a_rp_gsm_a_rp_rp_message_reference` | auto | medium | 6 |
| `nas.gsm_a_dtap.gsm_a_dtap_gsm_a_dtap_rpdu` | auto | medium | 47 |
| `nas.gsm_a_rp.gsm_a_rp_gsm_a_rp_tpdu` | auto | medium | 41 |
| `nas.esm_qci` | auto | medium | 8 |
| `nas.gsm_a_dtap_gsm_a_dtap_time_zone_time` | auto | high | 69 |
| `nas.emm_nonce` | auto | medium | 38 |
| `DedicatedInfoNAS` | auto | high | 63 |
| `nas.esm_pdn_ipv4` | auto | medium | 32 |
| `c_RNTI` | auto | medium | 41 |
| `shortMAC_I` | auto | medium | 41 |
| `nas.gsm_sms.gsm_sms_gsm_sms_tp_user_data_length` | auto | medium | 24 |
| `nas.gsm_sms.gsm_sms_gsm_sms_sms_text` | auto | medium | 28 |
| `nas.gsm_sms.gsm_sms_gsm_sms_dis_field_addr_length` | auto | medium | 9 |
| `nas.emm_hash_mme` | auto | medium | 15 |
| `nas.gsm_sms.gsm_sms_gsm_sms_scts` | auto | medium | 27 |
| `nas.gsm_sms.gsm_sms_gsm_sms_tp-oa` | auto | medium | 12 |
| `nas.gsm_sms.gsm_sms_gsm_sms_scts_seconds` | auto | medium | 19 |
| `nas.gsm_sms.gsm_sms_gsm_sms_scts_hour` | auto | medium | 13 |
| `nas.gsm_sms.gsm_sms_gsm_sms_scts_day` | auto | medium | 11 |
| `nas.gsm_sms.gsm_sms_gsm_sms_scts_minutes` | auto | medium | 19 |
| `nas.gsm_a_rp.gsm_a_dtap_gsm_a_dtap_clg_party_bcd_num` | auto | medium | 8 |
| `eutra` | auto | medium | 8 |
| `nas.gsm_a_gm_gsm_a_gm_sm_pco_dns_ipv6` | auto | medium | 9 |
| `nas.gsm_a_gm_gsm_a_gm_sm_pco_pcscf_ipv6` | auto | medium | 12 |
| `nas.gsm_a_gm_gsm_a_gm_sm_tft_packet_filter_component_type_id` | auto | medium | 8 |
| `nas.esm_pdn_ipv6_if_id` | auto | medium | 16 |
| `measResultList_r9` | auto | medium | 6 |
| `nas.gsm_a_gm_gsm_a_gm_sm_pco_pcscf_ipv4` | auto | medium | 10 |
| `nas.gsm_sms.gsm_sms_gsm_sms_fragment` | auto | medium | 12 |
| `nas.gsm_a_dtap.gsm_a_dtap_gsm_a_dtap_message_elements` | auto | medium | 11 |
| `timeConnFailure_r10` | auto | medium | 7 |
| `nas.gsm_a_gm_gsm_a_gm_sm_tft_packet_evaluation_precedence` | auto | medium | 7 |

### Mobility / reselection (27)

| field | source | cardinality | distinct values |
|---|---|---|---|
| `cellReselectionPriority` | auto | medium | 8 |
| `neighCellConfig` | curated | low | 3 |
| `t_ReselectionEUTRA` | curated | low | 3 |
| `threshX_High` | auto | medium | 11 |
| `threshX_Low` | auto | medium | 13 |
| `q_Hyst` | curated | low | 4 |
| `s_NonIntraSearch` | auto | medium | 17 |
| `q_QualMin_r9` | auto | medium | 8 |
| `s_IntraSearch` | auto | medium | 12 |
| `measResultNeighCells` | curated | low | 2 |
| `s_IntraSearchP_r9` | auto | medium | 6 |
| `s_NonIntraSearchQ_r9` | curated | low | 3 |
| `s_IntraSearchQ_r9` | curated | low | 2 |
| `s_NonIntraSearchP_r9` | curated | low | 5 |
| `threshX_Low_r15` | curated | low | 2 |
| `cellReselectionPriority_r15` | curated | low | 4 |
| `threshX_High_r15` | auto | medium | 10 |
| `interFreqNeighCellList` | auto | medium | 12 |
| `q_QualMin` | auto | medium | 6 |
| `intraFreqNeighCellList` | auto | medium | 11 |
| `threshX_HighQ_r9` | auto | medium | 6 |
| `threshX_LowQ_r9` | auto | medium | 6 |
| `neighCellConfig_r12` | curated | low | 2 |
| `t_ReselectionEUTRA_r12` | curated | low | 2 |
| `threshX_Low_r12` | curated | low | 5 |
| `threshX_High_r12` | curated | low | 4 |
| `cellReselectionPriority_r12` | curated | low | 2 |

### Measurement reporting config (23)

| field | source | cardinality | distinct values |
|---|---|---|---|
| `reportConfigId` | auto | medium | 21 |
| `measId` | auto | medium | 24 |
| `measObjectId` | auto | medium | 32 |
| `maxReportCells` | curated | low | 5 |
| `triggerType` | curated | low | 2 |
| `reportInterval` | auto | medium | 10 |
| `reportAmount` | curated | low | 5 |
| `reportConfig` | curated | low | 2 |
| `reportQuantity` | curated | low | 2 |
| `triggerQuantity` | curated | low | 2 |
| `eventId` | curated | low | 5 |
| `timeToTrigger` | auto | medium | 13 |
| `MeasId` | auto | medium | 32 |
| `ReportConfigId` | auto | medium | 21 |
| `measIdToAddModList` | auto | medium | 14 |
| `reportConfigToAddModList` | auto | medium | 14 |
| `measObjectToAddModList` | auto | medium | 12 |
| `measIdToRemoveList` | auto | medium | 20 |
| `reportConfigToRemoveList` | auto | medium | 19 |
| `measObjectEUTRA_offsetFreq` | auto | medium | 23 |
| `MeasObjectId` | auto | medium | 32 |
| `measObjectToRemoveList` | auto | medium | 13 |
| `cellForWhichToReportCGI` | auto | medium | 19 |

### Cell identity (14)

| field | source | cardinality | distinct values |
|---|---|---|---|
| `MCC_MNC_Digit` | auto | medium | 10 |
| `physCellId` | auto | high | 200+ |
| `e212_e212_mnc` | auto | medium | 21 |
| `e212_e212_mcc` | auto | medium | 16 |
| `cellIdentity` | auto | high | 200+ |
| `trackingAreaCode` | auto | high | 80 |
| `nas.e212_e212_mnc` | auto | medium | 9 |
| `targetPhysCellId` | auto | high | 200+ |
| `nas.e212_e212_tai_mnc` | auto | medium | 6 |
| `nas.e212_e212_tai_mcc` | auto | medium | 7 |
| `nas.e212_e212_gummei_mcc` | auto | medium | 7 |
| `nas.e212_e212_gummei_mnc` | auto | medium | 6 |
| `nas.e212_e212_lai_mnc` | auto | medium | 6 |
| `nas.e212_e212_lai_mcc` | auto | medium | 7 |

### Frequency / band (14)

| field | source | cardinality | distinct values |
|---|---|---|---|
| `freqBandIndicator` | auto | medium | 11 |
| `carrierFreq` | auto | high | 68 |
| `dl_CarrierFreq` | auto | high | 79 |
| `ul_CarrierFreq` | auto | medium | 16 |
| `interFreqCarrierFreqList` | auto | medium | 8 |
| `FreqBandIndicatorNR_r15` | auto | medium | 8 |
| `carrierFreq_r15` | auto | medium | 14 |
| `interFreqCarrierFreqList_v9e0` | auto | medium | 7 |
| `interFreqCarrierFreqList_v8h0` | auto | medium | 7 |
| `carrierFreqListUTRA_FDD` | auto | medium | 6 |
| `FreqBandIndicator_r11` | auto | medium | 12 |
| `dl_CarrierFreq_r12` | auto | medium | 11 |
| `nr-rrc_nr-rrc_FreqBandList` | auto | medium | 7 |
| `requestedFreqBandsNR_MRDC_r15` | auto | medium | 17 |

### Identity (12)

| field | source | cardinality | distinct values |
|---|---|---|---|
| `mmec` | auto | medium | 48 |
| `m_TMSI` | auto | high | 200+ |
| `IMSI_Digit` | auto | medium | 10 |
| `e212_e212_imsi` | auto | high | 200+ |
| `e212_e212_assoc_imsi` | auto | high | 200+ |
| `newUE_Identity` | auto | high | 200+ |
| `nas.3gpp_3gpp_tmsi` | auto | high | 200+ |
| `nas.emm_m_tmsi` | auto | high | 178 |
| `nas.e212_e212_assoc_imsi` | auto | medium | 7 |
| `nas.e212_e212_imsi` | auto | medium | 7 |
| `nas.gsm_a_gsm_a_imeisv` | auto | medium | 8 |
| `nas.gsm_a_gm_gsm_a_gm_gmm_ptmsi_sig` | auto | medium | 24 |

### Cause / Redirect / Barring codes (9)

| field | source | cardinality | distinct values |
|---|---|---|---|
| `cellReservedForOperatorUse` | manual | low | 2 |
| `cellBarred` | manual | constant | 1 |
| `establishmentCause` | manual | low | 3 |
| `releaseCause` | manual | constant | 1 |
| `nas.esm_cause` | manual | low | 4 |
| `nas.emm_cause` | manual | medium | 7 |
| `reestablishmentCause` | manual | low | 3 |
| `e_RedirectionUTRA_r9` | manual | constant | 1 |
| `redirectedCarrierInfo` | manual | low | 2 |

### Signal quality (6)

| field | source | cardinality | distinct values |
|---|---|---|---|
| `q_RxLevMin` | auto | medium | 13 |
| `rsrpResult` | auto | high | 92 |
| `rsrqResult` | auto | medium | 35 |
| `threshold_RSRP` | auto | medium | 39 |
| `threshold_RSRQ` | auto | medium | 25 |
| `rsrpResult_r9` | auto | medium | 9 |

### Timers / counters (5)

| field | source | cardinality | distinct values |
|---|---|---|---|
| `t301` | auto | medium | 7 |
| `defaultPagingCycle` | curated | low | 4 |
| `modificationPeriodCoeff` | curated | low | 3 |
| `drx_InactivityTimer` | auto | medium | 7 |
| `onDurationTimer` | auto | medium | 7 |

### Security (4)

| field | source | cardinality | distinct values |
|---|---|---|---|
| `nas.security_header_type` | auto | medium | 16 |
| `integrityProtAlgorithm` | manual | constant | 1 |
| `cipheringAlgorithm` | manual | low | 2 |
| `nas.ciphered_msg` | auto | high | 200+ |
