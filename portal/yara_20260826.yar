rule Hermes_Sleepwalker_Triage_20260826 {
    meta:
        description = "Triage-oriented signature for the SLEEPWALKER passive Windows backdoor described in August 2026 research"
        author = "Hermes CTI Agent"
        reference = "https://www.theregister.com/security/2026/08/24/you-dont-want-this-sleepwalker-backdoor-on-your-windows-machine/5292021"
        date = "2026-08-26"
        score = 80
        warning = "Research indicator only; validate against a known-good ESET Management Agent and sample context"

    strings:
        $magic = { 4D 5A }
        $s1 = "dpapisvc.dll" ascii wide nocase
        $s2 = "ERAAgent.exe" ascii wide nocase
        $s3 = "dpapi.dll" ascii wide nocase
        $s4 = "AES-256-CCM" ascii wide nocase

    condition:
        $magic at 0 and 2 of ($s*)
}
