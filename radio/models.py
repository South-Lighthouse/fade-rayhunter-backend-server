from django.db import models


class RadioCapture(models.Model):
    STATUS_PENDING = "pending"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_DONE, "Done"),
        (STATUS_ERROR, "Error"),
    ]

    session = models.OneToOneField(
        "captures.MonitoringSession", on_delete=models.CASCADE, related_name="radio_capture"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    pcap_path = models.CharField(max_length=500, blank=True)
    pcap_size = models.BigIntegerField(null=True, blank=True)
    packet_count = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reclaimed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.session}/radio"


class RadioPacket(models.Model):
    capture = models.ForeignKey(RadioCapture, on_delete=models.CASCADE, related_name="packets")
    sensor = models.ForeignKey("sensors.Sensor", on_delete=models.CASCADE, related_name="radio_packets")

    qmdl_timestamp = models.DateTimeField(null=True, blank=True)
    gps_timestamp = models.DateTimeField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    packet_type = models.CharField(max_length=64, db_index=True, blank=True)
    timing_advance = models.IntegerField(null=True, blank=True)

    # --- Generated fields, below, from radio/final_model_fields.tsv ---
    beta_offset_ri_index = models.BigIntegerField(null=True, blank=True)  # betaOffset_RI_Index
    c1 = models.BigIntegerField(null=True, blank=True)  # c1
    c_rnti = models.CharField(max_length=32, null=True, blank=True)  # c_RNTI
    carrier_freq_list_utra_fdd = models.BigIntegerField(null=True, blank=True)  # carrierFreqListUTRA_FDD
    cell_barred = models.BigIntegerField(null=True, blank=True)  # cellBarred
    cell_for_which_to_report_cgi = models.BigIntegerField(null=True, blank=True)  # cellForWhichToReportCGI
    cell_identity = models.CharField(max_length=32, null=True, blank=True)  # cellIdentity
    ciphering_algorithm = models.BigIntegerField(null=True, blank=True)  # cipheringAlgorithm
    cqi_pmi_config_index = models.BigIntegerField(null=True, blank=True)  # cqi_pmi_ConfigIndex
    cqi_pucch_resource_index = models.BigIntegerField(null=True, blank=True)  # cqi_PUCCH_ResourceIndex
    cqi_pucch_resource_index_r10 = models.BigIntegerField(null=True, blank=True)  # cqi_PUCCH_ResourceIndex_r10
    cyclic_shift = models.BigIntegerField(null=True, blank=True)  # cyclicShift
    data_data_data_data = models.CharField(max_length=32, null=True, blank=True)  # data.data_data_data
    default_paging_cycle = models.BigIntegerField(null=True, blank=True)  # defaultPagingCycle
    drx_inactivity_timer = models.BigIntegerField(null=True, blank=True)  # drx_InactivityTimer
    establishment_cause = models.BigIntegerField(null=True, blank=True)  # establishmentCause
    eutra = models.BigIntegerField(null=True, blank=True)  # eutra
    freq_band_indicator = models.BigIntegerField(null=True, blank=True)  # freqBandIndicator
    freq_domain_position = models.BigIntegerField(null=True, blank=True)  # freqDomainPosition
    freq_priority_list_eutra = models.BigIntegerField(null=True, blank=True)  # freqPriorityListEUTRA
    freq_priority_list_utra_fdd = models.BigIntegerField(null=True, blank=True)  # freqPriorityListUTRA_FDD
    gp0 = models.BigIntegerField(null=True, blank=True)  # gp0
    gp1 = models.BigIntegerField(null=True, blank=True)  # gp1
    hyper_sfn_r13 = models.CharField(max_length=32, null=True, blank=True)  # hyperSFN_r13
    integrity_prot_algorithm = models.BigIntegerField(null=True, blank=True)  # integrityProtAlgorithm
    inter_freq_carrier_freq_list = models.BigIntegerField(null=True, blank=True)  # interFreqCarrierFreqList
    inter_freq_carrier_freq_list_v8h0 = models.BigIntegerField(null=True, blank=True)  # interFreqCarrierFreqList_v8h0
    inter_freq_carrier_freq_list_v9e0 = models.BigIntegerField(null=True, blank=True)  # interFreqCarrierFreqList_v9e0
    intra_freq_excluded_cell_list = models.BigIntegerField(null=True, blank=True)  # intraFreqExcludedCellList
    intra_freq_neigh_cell_list = models.BigIntegerField(null=True, blank=True)  # intraFreqNeighCellList
    late_non_critical_extension = models.CharField(max_length=32, null=True, blank=True)  # lateNonCriticalExtension
    max_harq_tx = models.BigIntegerField(null=True, blank=True)  # maxHARQ_Tx
    meas_id_to_add_mod_list = models.BigIntegerField(null=True, blank=True)  # measIdToAddModList
    meas_id_to_remove_list = models.BigIntegerField(null=True, blank=True)  # measIdToRemoveList
    meas_object_to_add_mod_list = models.BigIntegerField(null=True, blank=True)  # measObjectToAddModList
    meas_object_to_remove_list = models.BigIntegerField(null=True, blank=True)  # measObjectToRemoveList
    meas_result_list_eutra = models.BigIntegerField(null=True, blank=True)  # measResultListEUTRA
    meas_result_neigh_cells = models.BigIntegerField(null=True, blank=True)  # measResultNeighCells
    mmegi = models.CharField(max_length=32, null=True, blank=True)  # mmegi
    modification_period_coeff = models.BigIntegerField(null=True, blank=True)  # modificationPeriodCoeff
    n1_pucch_an = models.BigIntegerField(null=True, blank=True)  # n1PUCCH_AN
    n4_tx_antenna_tm4 = models.CharField(max_length=32, null=True, blank=True)  # n4TxAntenna_tm4
    n_rb_cqi = models.BigIntegerField(null=True, blank=True)  # nRB_CQI
    nas_bearer_id = models.BigIntegerField(null=True, blank=True)  # nas.bearer_id
    nas_ciphered_msg = models.CharField(max_length=32, null=True, blank=True)  # nas.ciphered_msg
    nas_e212_e212_assoc_imsi = models.BigIntegerField(null=True, blank=True)  # nas.e212_e212_assoc_imsi
    nas_e212_e212_gummei_mcc = models.BigIntegerField(null=True, blank=True)  # nas.e212_e212_gummei_mcc
    nas_e212_e212_gummei_mnc = models.BigIntegerField(null=True, blank=True)  # nas.e212_e212_gummei_mnc
    nas_e212_e212_imsi = models.BigIntegerField(null=True, blank=True)  # nas.e212_e212_imsi
    nas_e212_e212_lai_mcc = models.BigIntegerField(null=True, blank=True)  # nas.e212_e212_lai_mcc
    nas_e212_e212_lai_mnc = models.BigIntegerField(null=True, blank=True)  # nas.e212_e212_lai_mnc
    nas_e212_e212_tai_mcc = models.BigIntegerField(null=True, blank=True)  # nas.e212_e212_tai_mcc
    nas_e212_e212_tai_mnc = models.BigIntegerField(null=True, blank=True)  # nas.e212_e212_tai_mnc
    nas_emm_cause = models.BigIntegerField(null=True, blank=True)  # nas.emm_cause
    nas_emm_esm_msg_cont = models.CharField(max_length=32, null=True, blank=True)  # nas.emm_esm_msg_cont
    nas_emm_hash_mme = models.CharField(max_length=32, null=True, blank=True)  # nas.emm_hash_mme
    nas_emm_m_tmsi = models.BigIntegerField(null=True, blank=True)  # nas.emm_m_tmsi
    nas_emm_mme_code = models.BigIntegerField(null=True, blank=True)  # nas.emm_mme_code
    nas_emm_mme_grp_id = models.BigIntegerField(null=True, blank=True)  # nas.emm_mme_grp_id
    nas_emm_nas_key_set_id = models.BigIntegerField(null=True, blank=True)  # nas.emm_nas_key_set_id
    nas_emm_nas_msg_cont = models.CharField(max_length=32, null=True, blank=True)  # nas.emm_nas_msg_cont
    nas_emm_res = models.CharField(max_length=32, null=True, blank=True)  # nas.emm_res
    nas_emm_short_mac = models.CharField(max_length=32, null=True, blank=True)  # nas.emm_short_mac
    nas_emm_tai_tac = models.BigIntegerField(null=True, blank=True)  # nas.emm_tai_tac
    nas_esm_apn_ambr_dl_ext = models.BigIntegerField(null=True, blank=True)  # nas.esm_apn_ambr_dl_ext
    nas_esm_apn_ambr_dl_total = models.BigIntegerField(null=True, blank=True)  # nas.esm_apn_ambr_dl_total
    nas_esm_cause = models.BigIntegerField(null=True, blank=True)  # nas.esm_cause
    nas_esm_pdn_ipv4 = models.CharField(max_length=32, null=True, blank=True)  # nas.esm_pdn_ipv4
    nas_esm_pdn_ipv6_if_id = models.CharField(max_length=32, null=True, blank=True)  # nas.esm_pdn_ipv6_if_id
    nas_esm_proc_trans_id = models.BigIntegerField(null=True, blank=True)  # nas.esm_proc_trans_id
    nas_esm_qci = models.BigIntegerField(null=True, blank=True)  # nas.esm_qci
    nas_gsm_a_dtap_gsm_a_dtap_autn = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_dtap_gsm_a_dtap_autn
    nas_gsm_a_dtap_gsm_a_dtap_autn_mac = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_dtap_gsm_a_dtap_autn_mac
    nas_gsm_a_dtap_gsm_a_dtap_autn_sqn_xor_ak = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_dtap_gsm_a_dtap_autn_sqn_xor_ak
    nas_gsm_a_dtap_gsm_a_dtap_gsm_a_dtap_msg_tp_type = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_dtap.gsm_a_dtap_gsm_a_dtap_msg_tp_type
    nas_gsm_a_dtap_gsm_a_dtap_gsm_a_dtap_rpdu = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_dtap.gsm_a_dtap_gsm_a_dtap_rpdu
    nas_gsm_a_dtap_gsm_a_dtap_gsm_a_dtap_tio = models.BigIntegerField(null=True, blank=True)  # nas.gsm_a_dtap.gsm_a_dtap_gsm_a_dtap_tio
    nas_gsm_a_dtap_gsm_a_dtap_number_of_spare_bits = models.BigIntegerField(null=True, blank=True)  # nas.gsm_a_dtap_gsm_a_dtap_number_of_spare_bits
    nas_gsm_a_dtap_gsm_a_dtap_rand = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_dtap_gsm_a_dtap_rand
    nas_gsm_a_dtap_gsm_a_dtap_text_string = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_dtap_gsm_a_dtap_text_string
    nas_gsm_a_dtap_gsm_a_dtap_time_zone_time = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_dtap_gsm_a_dtap_time_zone_time
    nas_gsm_a_dtap_gsm_a_gsm_a_len = models.BigIntegerField(null=True, blank=True)  # nas.gsm_a_dtap.gsm_a_gsm_a_len
    nas_gsm_a_dtap_gsm_a_gsm_a_skip_ind = models.BigIntegerField(null=True, blank=True)  # nas.gsm_a_dtap.gsm_a_gsm_a_skip_ind
    nas_gsm_a_gm_gsm_a_gm_sm_apn = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_gm_gsm_a_gm_sm_apn
    nas_gsm_a_gsm_a_imeisv = models.BigIntegerField(null=True, blank=True)  # nas.gsm_a_gsm_a_imeisv
    nas_gsm_a_gsm_a_lac = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_gsm_a_lac
    nas_gsm_a_rp_gsm_a_rp_gsm_a_rp_rp_message_reference = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_rp.gsm_a_rp_gsm_a_rp_rp_message_reference
    nas_gsm_a_rp_gsm_a_rp_gsm_a_rp_tpdu = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_a_rp.gsm_a_rp_gsm_a_rp_tpdu
    nas_gsm_sms_gsm_sms_gsm_sms_dis_field_addr_length = models.BigIntegerField(null=True, blank=True)  # nas.gsm_sms.gsm_sms_gsm_sms_dis_field_addr_length
    nas_gsm_sms_gsm_sms_gsm_sms_scts_day = models.BigIntegerField(null=True, blank=True)  # nas.gsm_sms.gsm_sms_gsm_sms_scts_day
    nas_gsm_sms_gsm_sms_gsm_sms_scts_hour = models.BigIntegerField(null=True, blank=True)  # nas.gsm_sms.gsm_sms_gsm_sms_scts_hour
    nas_gsm_sms_gsm_sms_gsm_sms_scts_minutes = models.BigIntegerField(null=True, blank=True)  # nas.gsm_sms.gsm_sms_gsm_sms_scts_minutes
    nas_gsm_sms_gsm_sms_gsm_sms_scts_seconds = models.BigIntegerField(null=True, blank=True)  # nas.gsm_sms.gsm_sms_gsm_sms_scts_seconds
    nas_gsm_sms_gsm_sms_gsm_sms_tp_oa = models.CharField(max_length=32, null=True, blank=True)  # nas.gsm_sms.gsm_sms_gsm_sms_tp-oa
    nas_gsm_sms_gsm_sms_gsm_sms_tp_user_data_length = models.BigIntegerField(null=True, blank=True)  # nas.gsm_sms.gsm_sms_gsm_sms_tp_user_data_length
    nas_ipcp_ipcp_ipcp_opt_pri_dns_address = models.CharField(max_length=32, null=True, blank=True)  # nas.ipcp.ipcp_ipcp_opt_pri_dns_address
    nas_ipcp_ipcp_ipcp_opt_sec_dns_address = models.CharField(max_length=32, null=True, blank=True)  # nas.ipcp.ipcp_ipcp_opt_sec_dns_address
    nas_ipcp_ipcp_opt_pri_dns = models.CharField(max_length=32, null=True, blank=True)  # nas.ipcp.ipcp_opt_pri_dns
    nas_ipcp_ipcp_opt_sec_dns = models.CharField(max_length=32, null=True, blank=True)  # nas.ipcp.ipcp_opt_sec_dns
    nas_msg_auth_code = models.CharField(max_length=32, null=True, blank=True)  # nas.msg_auth_code
    nas_nas_msg_emm_type = models.CharField(max_length=32, null=True, blank=True)  # nas.nas_msg_emm_type
    nas_nas_msg_esm_type = models.CharField(max_length=32, null=True, blank=True)  # nas.nas_msg_esm_type
    nas_seq_no = models.BigIntegerField(null=True, blank=True)  # nas.seq_no
    nas_seq_no_short = models.BigIntegerField(null=True, blank=True)  # nas.seq_no_short
    new_ue_identity = models.CharField(max_length=32, null=True, blank=True)  # newUE_Identity
    next_hop_chaining_count = models.BigIntegerField(null=True, blank=True)  # nextHopChainingCount
    nom_pdsch_rs_epre_offset = models.BigIntegerField(null=True, blank=True)  # nomPDSCH_RS_EPRE_Offset
    nr_rrc_nr_rrc_band_nr = models.BigIntegerField(null=True, blank=True)  # nr-rrc_nr-rrc_bandNR
    nr_rrc_nr_rrc_freq_band_list = models.BigIntegerField(null=True, blank=True)  # nr-rrc_nr-rrc_FreqBandList
    number_of_preambles_sent_r16 = models.BigIntegerField(null=True, blank=True)  # numberOfPreamblesSent_r16
    number_of_ra_preambles = models.BigIntegerField(null=True, blank=True)  # numberOfRA_Preambles
    on_duration_timer = models.BigIntegerField(null=True, blank=True)  # onDurationTimer
    p0_nominal_pucch = models.BigIntegerField(null=True, blank=True)  # p0_NominalPUCCH
    p0_nominal_pusch = models.BigIntegerField(null=True, blank=True)  # p0_NominalPUSCH
    p_a = models.BigIntegerField(null=True, blank=True)  # p_a
    paging_record_list = models.BigIntegerField(null=True, blank=True)  # pagingRecordList
    prach_config_index = models.BigIntegerField(null=True, blank=True)  # prach_ConfigIndex
    prach_freq_offset = models.BigIntegerField(null=True, blank=True)  # prach_FreqOffset
    preamble_initial_received_target_power = models.BigIntegerField(null=True, blank=True)  # preambleInitialReceivedTargetPower
    pusch_hopping_offset = models.BigIntegerField(null=True, blank=True)  # pusch_HoppingOffset
    q_hyst = models.BigIntegerField(null=True, blank=True)  # q_Hyst
    ra_preamble_index = models.BigIntegerField(null=True, blank=True)  # ra_PreambleIndex
    random_value = models.CharField(max_length=32, null=True, blank=True)  # randomValue
    redirected_carrier_info = models.BigIntegerField(null=True, blank=True)  # redirectedCarrierInfo
    reestablishment_cause = models.BigIntegerField(null=True, blank=True)  # reestablishmentCause
    reference_signal_power = models.BigIntegerField(null=True, blank=True)  # referenceSignalPower
    release_cause = models.BigIntegerField(null=True, blank=True)  # releaseCause
    report_config_to_add_mod_list = models.BigIntegerField(null=True, blank=True)  # reportConfigToAddModList
    report_config_to_remove_list = models.BigIntegerField(null=True, blank=True)  # reportConfigToRemoveList
    requested_freq_bands_nr_mrdc_r15 = models.CharField(max_length=32, null=True, blank=True)  # requestedFreqBandsNR_MRDC_r15
    ri_config_index = models.BigIntegerField(null=True, blank=True)  # ri_ConfigIndex
    root_sequence_index = models.BigIntegerField(null=True, blank=True)  # rootSequenceIndex
    rrc_rrc_start_cs = models.CharField(max_length=32, null=True, blank=True)  # rrc_rrc_start_CS
    rrc_rrc_start_ps = models.CharField(max_length=32, null=True, blank=True)  # rrc_rrc_start_PS
    rsrp_result_r9 = models.BigIntegerField(null=True, blank=True)  # rsrpResult_r9
    s_intra_search = models.BigIntegerField(null=True, blank=True)  # s_IntraSearch
    s_intra_search_p_r9 = models.BigIntegerField(null=True, blank=True)  # s_IntraSearchP_r9
    s_intra_search_q_r9 = models.BigIntegerField(null=True, blank=True)  # s_IntraSearchQ_r9
    s_non_intra_search = models.BigIntegerField(null=True, blank=True)  # s_NonIntraSearch
    s_non_intra_search_p_r9 = models.BigIntegerField(null=True, blank=True)  # s_NonIntraSearchP_r9
    s_non_intra_search_q_r9 = models.BigIntegerField(null=True, blank=True)  # s_NonIntraSearchQ_r9
    scheduling_info_list = models.BigIntegerField(null=True, blank=True)  # schedulingInfoList
    sf320 = models.BigIntegerField(null=True, blank=True)  # sf320
    sf40 = models.BigIntegerField(null=True, blank=True)  # sf40
    short_mac_i = models.CharField(max_length=32, null=True, blank=True)  # shortMAC_I
    size_of_ra_preambles_group_a = models.BigIntegerField(null=True, blank=True)  # sizeOfRA_PreamblesGroupA
    sr_config_index = models.BigIntegerField(null=True, blank=True)  # sr_ConfigIndex
    sr_pucch_resource_index = models.BigIntegerField(null=True, blank=True)  # sr_PUCCH_ResourceIndex
    sr_subframe_offset = models.BigIntegerField(null=True, blank=True)  # sr_SubframeOffset
    srs_config_index = models.BigIntegerField(null=True, blank=True)  # srs_ConfigIndex
    srs_subframe_config = models.BigIntegerField(null=True, blank=True)  # srs_SubframeConfig
    system_info_value_tag = models.BigIntegerField(null=True, blank=True)  # systemInfoValueTag
    t301 = models.BigIntegerField(null=True, blank=True)  # t301
    target_phys_cell_id = models.BigIntegerField(null=True, blank=True)  # targetPhysCellId
    thresh_serving_low = models.BigIntegerField(null=True, blank=True)  # threshServingLow
    time_conn_failure_r10 = models.BigIntegerField(null=True, blank=True)  # timeConnFailure_r10
    tracking_area_code = models.CharField(max_length=32, null=True, blank=True)  # trackingAreaCode
    ue_capability_rat_container = models.CharField(max_length=32, null=True, blank=True)  # ueCapabilityRAT_Container
    ul_carrier_freq = models.BigIntegerField(null=True, blank=True)  # ul_CarrierFreq
    zero_correlation_zone_config = models.BigIntegerField(null=True, blank=True)  # zeroCorrelationZoneConfig
    # --- end generated fields ---

    raw_fields = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["capture", "qmdl_timestamp"]
        indexes = [
            models.Index(fields=["capture", "packet_type"]),
            models.Index(fields=["sensor", "qmdl_timestamp"]),
        ]

    def __str__(self):
        return f"{self.sensor.slug}/{self.capture_id}#{self.pk}"
