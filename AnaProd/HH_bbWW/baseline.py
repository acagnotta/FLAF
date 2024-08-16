from Common.Utilities import *

channels = [ 'muMu', 'eMu', 'eE', 'mu', 'e' ] # in order of importance during the channel selection
leg_names = [ "Electron", "Muon" ]

def getChannelLegs(channel):
    ch_str = channel.lower()
    legs = []
    while len(ch_str) > 0:
        name_idx = None
        obj_name = None
        for idx, obj in enumerate([ 'e', 'mu' ]):
            if ch_str.startswith(obj):
                name_idx = idx
                obj_name = obj
                break
        if name_idx is None:
            raise RuntimeError(f"Invalid channel name {channel}")
        legs.append(leg_names[name_idx])
        ch_str = ch_str[len(obj_name):]
    return legs


def RecoHWWCandidateSelection(df):
    df = df.Define("Electron_presel", """
        v_ops::pt(Electron_p4) > 10 && abs(v_ops::eta(Electron_p4)) < 2.5 && abs(Electron_dz) < 0.1 && abs(Electron_dxy) < 0.05 && Electron_sip3d <= 8 && Electron_miniPFRelIso_all < 0.4 && Electron_mvaIso_WP90""")

    df = df.Define("Muon_presel", """
        v_ops::pt(Muon_p4) > 15 && abs(v_ops::eta(Muon_p4)) < 2.4 && abs(Muon_dz) < 0.1 && abs(Muon_dxy) < 0.05 && abs(Muon_dxy) < 0.05 && Muon_sip3d <= 8 && Muon_miniPFRelIso_all < 0.4 && Muon_looseId""")

    df = df.Define("Electron_sel", f"""
        (Electron_presel && Electron_mvaIso_WP80)""")

    df = df.Define("Muon_sel", f"""
        (Muon_presel && Muon_tightId)""")
    df = df.Define("Electron_iso", "Electron_miniPFRelIso_all") \
           .Define("Muon_iso", "Muon_miniPFRelIso_all")

    df = df.Define("N_sel_Ele", "Electron_pt[Electron_sel].size()")
    df = df.Define("N_sel_Mu", "Muon_pt[Muon_sel].size()")
    df = df.Define("N_sel_lep", "N_sel_Ele + N_sel_Mu")
    cand_columns = []
    for ch in channels:
        legs = getChannelLegs(ch)
        cand_column = f"HwwCandidates_{ch}"
        leg_args = []
        for leg_idx, leg in enumerate(legs):
            leg_args.extend([f"{leg}_sel", f"{leg}_p4", f"{leg}_iso", f"{leg}_charge", f"{leg}_genMatchIdx"])
        leg_str = ', '.join(leg_args)
        df = df.Define(cand_column, f"GetHWWCandidates(Channel::{ch}, 0.4, {leg_str})")
        cand_columns.append(cand_column)
    cand_filters = [ f'{c}.size() > 0' for c in cand_columns ]
    stringfilter = " || ".join(cand_filters)
    df = df.Filter(stringfilter, "Reco Baseline 2")
    cand_list_str = ', '.join([ '&' + c for c in cand_columns])
    df = df.Define('HwwCandidate', f'GetBestHWWCandidate({{ {cand_list_str} }}, event)')
    df = df.Define("is_SL", "HwwCandidate.leg_type.size() == 1")
    return df

def RecoHWWJetSelection(df):
    df = df.Define("Jet_Incl", f"v_ops::pt(Jet_p4)>20 && abs(v_ops::eta(Jet_p4)) < 2.5 && ( Jet_jetId & 2 )")
    df = df.Define("FatJet_Incl", "(v_ops::pt(FatJet_p4)>200 && abs(v_ops::eta(FatJet_p4)) < 2.5 ) && ( FatJet_jetId & 2 ) && (FatJet_msoftdrop > 30) ")
    df = df.Define("Jet_sel", """return RemoveOverlaps(Jet_p4, Jet_Incl,HwwCandidate.getLegP4s(), 0.4);""")
    df = df.Define("FatJet_sel", """return RemoveOverlaps(FatJet_p4, FatJet_Incl,HwwCandidate.getLegP4s(), 0.4);""")
    df = df.Define("Jet_cleaned", " RemoveOverlaps(Jet_p4, Jet_sel,{ {FatJet_p4[FatJet_sel][0], },}, 1, 0.8)")

    df = df.Define("n_eff_Jets", "(FatJet_p4[FatJet_sel].size()*2)+(Jet_p4[Jet_cleaned].size())")
    df = df.Define("n_eff_jets_SL","(is_SL && n_eff_Jets>=3)")
    df = df.Define("n_eff_jets_DL","(!is_SL && n_eff_Jets>=2)")

    return df.Filter(" (n_eff_jets_SL || n_eff_jets_DL)", "Reco bjet candidates")

def ThirdLeptonVeto(df):
    df = df.Define("Electron_vetoSel",
                   f"""v_ops::pt(Electron_p4) > 10 && abs(v_ops::eta(Electron_p4)) < 2.5 && abs(Electron_dz) < 0.2 && abs(Electron_dxy) < 0.045
                      && ( Electron_mvaIso_WP90 == true )
                     && (HttCandidate.isLeg(Electron_idx, Leg::e)== false)""")
    df = df.Filter("Electron_idx[Electron_vetoSel].size() == 0", "No extra electrons")
    df = df.Define("Muon_vetoSel",
                   f"""v_ops::pt(Muon_p4) > 10 && abs(v_ops::eta(Muon_p4)) < 2.4 && abs(Muon_dz) < 0.2 && abs(Muon_dxy) < 0.045
                      && ( Muon_mediumId || Muon_tightId ) && Muon_pfRelIso04_all<0.3
                      && (HttCandidate.isLeg(Muon_idx, Leg::mu) == false)""")
    df = df.Filter("Muon_idx[Muon_vetoSel].size() == 0", "No extra muons")
    return df

def ExtraRecoJetSelection(df):
    df = df.Define("ExtraJet_B0", f"v_ops::pt(Jet_p4)>20 && abs(v_ops::eta(Jet_p4)) < 5 && ( Jet_jetId & 2 )")
    df = df.Define(f"ObjectsToRemoveOverlap_DL", "if(Hbb_isValid){return std::vector<RVecLV>({{HwwCandidate.leg_p4[0], HwwCandidate.leg_p4[1],HbbCandidate->leg_p4[0],HbbCandidate->leg_p4[1]}}); } return std::vector<RVecLV>({{HwwCandidate.leg_p4[0], HwwCandidate.leg_p4[1]}})")
    df = df.Define(f"ObjectsToRemoveOverlap_SL", "if(Hbb_isValid){return std::vector<RVecLV>({{HwwCandidate.leg_p4[0],HbbCandidate->leg_p4[0],HbbCandidate->leg_p4[1]}}); } return std::vector<RVecLV>({{HwwCandidate.leg_p4[0]}})")
    df = df.Define("ExtraJet_B1", """if (is_SL)
                                        return RemoveOverlaps(Jet_p4, ExtraJet_B0,ObjectsToRemoveOverlap_SL,2,0.4);
                                    return RemoveOverlaps(Jet_p4, ExtraJet_B0,ObjectsToRemoveOverlap_DL,2,0.4); """)
    return df
def ApplyJetSelection(df):
    return df.Filter("Jet_idx[Jet_bCand].size()>=2 || FatJet_idx[FatJet_bbCand].size()>=1", "Reco bjet candidates")

def GenRecoJetMatching(df):
    df = df.Define("Jet_genJetIdx_matched", "GenRecoJetMatching(event,Jet_idx, GenJet_idx, Jet_bCand, GenJet_B2, GenJet_p4, Jet_p4 , 0.3)")
    df = df.Define("Jet_genMatched", "Jet_genJetIdx_matched>=0")
    return df.Filter("Jet_genJetIdx_matched[Jet_genMatched].size()>=2", "Two different gen-reco jet matches at least")

def DefineHbbCand(df):
    df = df.Define("HbbCandidate", "GetHbbCandidate(Jet_btagPNetB, Jet_sel, Jet_p4, Jet_idx)")
    return df
