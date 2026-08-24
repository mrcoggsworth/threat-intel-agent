rule Hermes_QUICSILVER_QUICAgent_Triage {
    meta:
        description = "Triage-only rule for QUICAgent and Operation QUICSILVER artifacts reported by Seqrite"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://www.seqrite.com/blog/operation-quicsilver-china-nexus-actor-targets-myanmar-diplomats-via-vhd-delivered-go-backdoor/"
        date = "2026-08-24"
        confidence = "medium; validate against samples"
    strings:
        $pe = { 4D 5A }
        $c2_worker1 = "appupdate.0cmds20cj2cdf8.workers.dev" ascii wide nocase
        $c2_worker2 = "regupdate.eamakfu49dc28wa.workers.dev" ascii wide nocase
        $c2_domain = "register.mediumser.com" ascii wide nocase
        $implant = "Windowsupdate.exe" ascii wide nocase
        $startup = "SystemIn.lnk" ascii wide nocase
        $ca = "RAT CA" ascii wide
        $rc4_key = "MySecretEncryptionKey2025!@#$%" ascii
    condition:
        $pe at 0 and 2 of ($c2_*, $implant, $startup, $ca, $rc4_key)
}
