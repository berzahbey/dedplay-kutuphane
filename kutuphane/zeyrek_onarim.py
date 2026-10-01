"""zeyrek 0.1.3 hatasının düzeltmesi: çözümleme, kök kaydının ses özellikleri kümesini (StemTransition.attrs) kopyalamadan
kullanıyor; ekin yüzeyi kelimenin kalanına eşitse (rulebasedanalyzer: tail_equals_surface) kümeye eklenen özellik
(ör. ExpectsConsonant) kök kaydına kalıcı yazılıyor. Sonuç: "olmak" bir kez çözümlenince "olanlar", "olacak" gibi
"ol-" kökünden doğru kelimeler geçersiz sayılıyor. Düzeltme: arama kök kümesinin kopyasıyla başlar."""
try:
    from zeyrek import morphotactics as _mt

    if not getattr(_mt.SearchPath, "_dedplay_onarim", False):
        _asil_initial = _mt.SearchPath.initial.__func__

        @classmethod
        def _initial(cls, stem_transition, tail):
            yol = _asil_initial(cls, stem_transition, tail)
            yol.phonetic_attributes = set(yol.phonetic_attributes)  # kök kaydının kümesi değil, kopyası
            return yol

        _mt.SearchPath.initial = _initial
        _mt.SearchPath._dedplay_onarim = True
except Exception:  # zeyrek yoksa ya da yapısı değiştiyse dokunma
    pass
