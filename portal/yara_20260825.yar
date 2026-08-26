rule Hermes_E4del_PINHOLE_Triage {
    meta:
        description = "Triage rule for E4del and PINHOLE RAT delivery artifacts reported through FTP banner dead drops"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://thehackernews.com/2026/08/e4del-and-pinhole-rats-turn-ftp-banners.html"
        date = "2026-08-25"
        confidence = "medium; validate against samples"
    strings:
        $pe = { 4D 5A }
        $ftp1 = "157.254.194.31" ascii wide nocase
        $ftp2 = "167.148.41.164" ascii wide nocase
        $ftp3 = "209.99.185.38" ascii wide nocase
        $c2 = "cloudflare.milicare.in" ascii wide nocase
        $com = "MSXML2.XMLHTTP" ascii wide nocase
        $rat1 = "E4del" ascii wide nocase
        $rat2 = "PINHOLE" ascii wide nocase
    condition:
        $pe at 0 and 2 of ($ftp*, $c2, $com, $rat*)
}

rule Hermes_Unit42_AI_Malware_PDB_Triage {
    meta:
        description = "Conservative triage rule for PDB project strings observed in Unit 42 AI-enabled malware analysis"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://unit42.paloaltonetworks.com/ai-enabled-malware-analysis/"
        date = "2026-08-25"
        confidence = "low-to-medium; PDB strings are not unique identifiers"
    strings:
        $pe = { 4D 5A }
        $pdb1 = "Dev.pdb" ascii wide nocase
        $pdb2 = "Funksec.pdb" ascii wide nocase
        $pdb3 = "Darkzone.pdb" ascii wide nocase
        $pdb4 = "Darkfunk.pdb" ascii wide nocase
    condition:
        $pe at 0 and 2 of ($pdb*)
}
