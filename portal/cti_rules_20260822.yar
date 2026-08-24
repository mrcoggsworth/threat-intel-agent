rule Hermes_RedC2_Npm_RedShell_Triage {
    meta:
        description = "Triage RedShell ELF payloads delivered through trojanized npm packages"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://www.trendaisecurity.com/en-us/resources-insights/trendai-security-blog/redc2-ai-powered-linux-implant"
        date = "2026-08-22"
        confidence = "medium; validate package and binary provenance"
    strings:
        $elf = { 7F 45 4C 46 }
        $s_redshell = "RedShell" ascii wide nocase
        $s_loader = "dist/index.mjs" ascii wide nocase
        $s_math = "math-core.bin" ascii wide nocase
        $s_pkg = "streak-metrics-math" ascii wide nocase
        $s_agent = "Red Agent" ascii wide nocase
    condition:
        $elf at 0 and 2 of ($s_*)
}

rule Hermes_SynkLoader_Windows_Triage {
    meta:
        description = "Triage SynkLoader MSI/Python/PowerShell components"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://expel.com/blog/synkloader-when-you-throw-in-everything-but-the-kitchen-sink/"
        date = "2026-08-22"
        confidence = "medium; use source hashes for exact matching"
    strings:
        $pe = { 4D 5A }
        $s_cleaner = "PowershellCleaner" ascii wide nocase
        $s_script = "cleaner.ps1" ascii wide nocase
        $s_archive = "archive6.zip" ascii wide nocase
        $s_dll1 = "msvcp150.dll" ascii wide nocase
        $s_dll2 = "msvcp160.dll" ascii wide nocase
        $s_pdb = "pwshnewdll.pdb" ascii wide nocase
        $s_phish = "PhishLocker" ascii wide nocase
        $s_c2 = "neversoftmain.net" ascii wide nocase
    condition:
        $pe at 0 and 3 of ($s_*)
}

rule Hermes_BTR_Driver_Weaponization_Triage {
    meta:
        description = "Triage BTR.sys remediation-driver abuse artifacts"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://research.checkpoint.com/2026/btr-reforged-weaponizing-defenders-remediation-driver-as-a-kernel-operation-primitive/"
        date = "2026-08-22"
        confidence = "low-medium; legitimate Defender remediation may match"
    strings:
        $pe = { 4D 5A }
        $s_btr = "BTR.sys" ascii wide nocase
        $s_ads = ":changelist" ascii wide nocase
        $s_service = "CurrentControlSet\\Services\\" ascii wide nocase
        $s_mp = "MpEngine.dll" ascii wide nocase
        $s_log = "BootClean.log" ascii wide nocase
    condition:
        $pe at 0 and 2 of ($s_*)
}
