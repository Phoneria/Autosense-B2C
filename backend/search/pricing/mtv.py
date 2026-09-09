def hesapla_mtv(motor_hacmi_cc: int = None, 
                motor_gucu_kw: int = None,
                tasit_degeri_tl: int = 0, 
                arac_yasi: int = 1,
                yakit_tipi: str = "benzin") -> dict:
    """
    2026 MTV Tarifesine göre Motorlu Taşıtlar Vergisi hesaplar
    (2025 tarifesi + %25.5 zam)
    
    Args:
        motor_hacmi_cc: Motor silindir hacmi (cm3) - benzin/dizel için
        motor_gucu_kw: Motor gücü (kW) - elektrikli için
        tasit_degeri_tl: Taşıt değeri (TL)
        arac_yasi: Araç yaşı (yıl)
        yakit_tipi: "benzin", "dizel", "elektrik"
    
    Returns:
        dict: MTV hesaplama detayları
    """
    
    # %25.5 zam katsayısı
    ZAM_KATSAYISI = 1.255
    
    # =========================================================================
    # BENZİN / DİZEL TARİFESİ (2026 = 2025 + %25.5)
    # =========================================================================
    tarife_benzin_2025 = [
        # 1300 cm3 ve aşağısı
        (0, 1300, 0, 309100, [5750, 4010, 2238, 1689, 593]),
        (0, 1300, 309100, 541500, [6319, 4409, 2459, 1861, 655]),
        (0, 1300, 541500, float('inf'), [6902, 4807, 2693, 2032, 706]),
        
        # 1301 - 1600 cm3
        (1301, 1600, 0, 309100, [10016, 7510, 4354, 3077, 1181]),
        (1301, 1600, 309100, 541500, [11023, 8264, 4794, 3375, 1290]),
        (1301, 1600, 541500, float('inf'), [12028, 9012, 5220, 3685, 1408]),
        
        # 1601 - 1800 cm3
        (1601, 1800, 0, 775100, [19472, 15226, 8948, 5458, 2113]),
        (1601, 1800, 775100, float('inf'), [21251, 16600, 9775, 5964, 2307]),
        
        # 1801 - 2000 cm3
        (1801, 2000, 0, 775100, [30679, 23625, 13886, 8264, 3248]),
        (1801, 2000, 775100, float('inf'), [33474, 25784, 15147, 9012, 3547]),
        
        # 2001 - 2500 cm3
        (2001, 2500, 0, 968100, [46027, 33413, 20874, 12465, 4930]),
        (2001, 2500, 968100, float('inf'), [50217, 36448, 22768, 13606, 5378]),
        
        # 2501 - 3000 cm3
        (2501, 3000, 0, 1937500, [64175, 55837, 34878, 18758, 6875]),
        (2501, 3000, 1937500, float('inf'), [70018, 60905, 38053, 20466, 7503]),
        
        # 3001 - 3500 cm3
        (3001, 3500, 0, 1937500, [97744, 87954, 52976, 26443, 9684]),
        (3001, 3500, 1937500, float('inf'), [106641, 95940, 57791, 28839, 10578]),
        
        # 3501 - 4000 cm3
        (3501, 4000, 0, 3101800, [153684, 132712, 78152, 34878, 13886]),
        (3501, 4000, 3101800, float('inf'), [167671, 144770, 85271, 38053, 15147]),
        
        # 4001 cm3 ve yukarısı
        (4001, float('inf'), 0, 3683200, [251554, 188627, 111714, 50206, 19472]),
        (4001, float('inf'), 3683200, float('inf'), [274415, 205781, 121873, 54769, 21251]),
    ]
    
    # 2026 tarifesi (%25.5 zamlı)
    tarife_benzin = []
    for row in tarife_benzin_2025:
        motor_min, motor_max, deger_min, deger_max, tutarlar = row
        tutarlar_zamli = [int(t * ZAM_KATSAYISI) for t in tutarlar]
        tarife_benzin.append((motor_min, motor_max, deger_min, deger_max, tutarlar_zamli))
    
    # =========================================================================
    # ELEKTRİKLİ ARAÇ TARİFESİ (2026 = 2025 + %25.5)
    # Format: (kw_min, kw_max, deger_min, deger_max, [1-3 yaş, 4-6 yaş])
    # =========================================================================
    tarife_elektrik_2025 = [
        # <70 kW
        (0, 69, 0, 114000, [1207, 840]),
        (0, 69, 114000, 199700, [1324, 926]),
        (0, 69, 199700, float('inf'), [1449, 1011]),
        
        # 70-85 kW
        (70, 85, 0, 114000, [2104, 1577]),
        (70, 85, 114000, 199700, [2314, 1737]),
        (70, 85, 199700, float('inf'), [2528, 1894]),
        
        # 85-105 kW
        (85, 105, 0, 285800, [4090, 3199]),
        (85, 105, 285800, float('inf'), [4463, 3491]),
        
        # 105-120 kW
        (105, 120, 0, 285800, [6446, 4964]),
        (105, 120, 285800, float('inf'), [7032, 5420]),
        
        # 120-150 kW
        (120, 150, 0, 356900, [9673, 7020]),
        (120, 150, 356900, float('inf'), [10554, 7659]),
        
        # 150-180 kW
        (150, 180, 0, 714300, [13487, 11733]),
        (150, 180, 714300, float('inf'), [14716, 12801]),
        
        # 180-210 kW
        (180, 210, 0, 714300, [20537, 18484]),
        (180, 210, 714300, float('inf'), [22411, 20177]),
        
        # 210-240 kW
        (210, 240, 0, 1143000, [32300, 27892]),
        (210, 240, 1143000, float('inf'), [35241, 30426]),
        
        # >240 kW
        (240, float('inf'), 0, 1357700, [52868, 39642]),
        (240, float('inf'), 1357700, float('inf'), [57671, 43248]),
    ]
    
    # 2026 tarifesi (%25.5 zamlı)
    tarife_elektrik = []
    for row in tarife_elektrik_2025:
        kw_min, kw_max, deger_min, deger_max, tutarlar = row
        tutarlar_zamli = [int(t * ZAM_KATSAYISI) for t in tutarlar]
        tarife_elektrik.append((kw_min, kw_max, deger_min, deger_max, tutarlar_zamli))
    
    # =========================================================================
    # HESAPLAMA
    # =========================================================================
    
    # Elektrikli mi benzinli mi?
    is_elektrik = yakit_tipi.lower() in ["elektrik", "electric", "ev"]
    
    if is_elektrik:
        # Elektrikli araç - sadece 1-6 yaş arası veri var
        if arac_yasi <= 3:
            yas_index = 0
            yas_grubu = "1-3 yaş"
        elif arac_yasi <= 6:
            yas_index = 1
            yas_grubu = "4-6 yaş"
        else:
            return {
                'error': 'Elektrikli araçlar için 7 yaş ve üzeri veri mevcut değil!',
                'not': 'Elektrikli araçlar görece yeni olduğundan tarife sadece 1-6 yaş için tanımlı.'
            }
        
        if motor_gucu_kw is None:
            return {'error': 'Elektrikli araç için motor_gucu_kw parametresi gerekli!'}
        
        deger = motor_gucu_kw
        birim = "kW"
        tarife = tarife_elektrik
        
    else:
        # Benzin/Dizel araç
        if arac_yasi <= 3:
            yas_index = 0
            yas_grubu = "1-3 yaş"
        elif arac_yasi <= 6:
            yas_index = 1
            yas_grubu = "4-6 yaş"
        elif arac_yasi <= 11:
            yas_index = 2
            yas_grubu = "7-11 yaş"
        elif arac_yasi <= 15:
            yas_index = 3
            yas_grubu = "12-15 yaş"
        else:
            yas_index = 4
            yas_grubu = "16+ yaş"
        
        if motor_hacmi_cc is None:
            return {'error': 'Benzin/dizel araç için motor_hacmi_cc parametresi gerekli!'}
        
        deger = motor_hacmi_cc
        birim = "cm³"
        tarife = tarife_benzin
    
    # Uygun tarife satırını bul
    for row in tarife:
        motor_min, motor_max, deger_min, deger_max, tutarlar = row
        
        # Motor aralığı kontrolü
        if motor_min <= deger <= motor_max or (motor_max == float('inf') and deger >= motor_min):
            # Taşıt değeri kontrolü
            if deger_min <= tasit_degeri_tl < deger_max or (deger_max == float('inf') and tasit_degeri_tl >= deger_min):
                
                if yas_index >= len(tutarlar):
                    return {'error': f'Bu yaş grubu için veri mevcut değil: {yas_grubu}'}
                
                mtv_tutar = tutarlar[yas_index]
                
                # Motor grubunu belirle
                if motor_max == float('inf'):
                    motor_grubu = f"{motor_min} {birim} ve üzeri"
                elif motor_min == 0:
                    motor_grubu = f"{motor_max} {birim} altı"
                else:
                    motor_grubu = f"{motor_min}-{motor_max} {birim}"
                
                # Değer aralığını belirle
                if deger_max == float('inf'):
                    deger_araligi = f"{deger_min:,.0f} TL üzeri".replace(",", ".")
                elif deger_min == 0:
                    deger_araligi = f"{deger_max:,.0f} TL altı".replace(",", ".")
                else:
                    deger_araligi = f"{deger_min:,.0f} - {deger_max:,.0f} TL".replace(",", ".")
                
                return {
                    'yakit_tipi': yakit_tipi,
                    'motor_degeri': deger,
                    'motor_birimi': birim,
                    'motor_grubu': motor_grubu,
                    'tasit_degeri': tasit_degeri_tl,
                    'deger_araligi': deger_araligi,
                    'arac_yasi': arac_yasi,
                    'yas_grubu': yas_grubu,
                    'mtv_tutari': mtv_tutar,
                    'mtv_formatted': f"{mtv_tutar:,.0f} TL".replace(",", "."),
                    'tarife_yili': 2026,
                    'not': '2025 tarifesi + %25.5 zam'
                }
    
    return {'error': f'Uygun tarife bulunamadı! Motor: {deger} {birim}, Değer: {tasit_degeri_tl} TL'}


# =============================================================================
# KULLANIM ÖRNEKLERİ
# =============================================================================

if __name__ == "__main__":
    
    print("=" * 60)
    print("2026 MTV HESAPLAMA (2025 + %25.5 ZAM)")
    print("=" * 60)
    
    # Örnek 1: Benzinli araç - 1.6L, 500.000 TL, 2 yaşında
    print("\n--- Örnek 1: Benzinli 1.6L ---")
    sonuc = hesapla_mtv(
        motor_hacmi_cc=1598,
        tasit_degeri_tl=500000,
        arac_yasi=2,
        yakit_tipi="benzin"
    )
    print(f"Motor: {sonuc['motor_grubu']}")
    print(f"Değer: {sonuc['deger_araligi']}")
    print(f"Yaş: {sonuc['yas_grubu']}")
    print(f"MTV: {sonuc['mtv_formatted']}")
    
    # Örnek 2: Dizel araç - 2.0L, 800.000 TL, 5 yaşında
    print("\n--- Örnek 2: Dizel 2.0L ---")
    sonuc = hesapla_mtv(
        motor_hacmi_cc=1995,
        tasit_degeri_tl=800000,
        arac_yasi=5,
        yakit_tipi="dizel"
    )
    print(f"Motor: {sonuc['motor_grubu']}")
    print(f"Değer: {sonuc['deger_araligi']}")
    print(f"Yaş: {sonuc['yas_grubu']}")
    print(f"MTV: {sonuc['mtv_formatted']}")
    
    # Örnek 3: Elektrikli - Tesla Model 3 (211 kW, 2.000.000 TL, 1 yaşında)
    print("\n--- Örnek 3: Tesla Model 3 (211 kW) ---")
    sonuc = hesapla_mtv(
        motor_gucu_kw=211,
        tasit_degeri_tl=2000000,
        arac_yasi=1,
        yakit_tipi="elektrik"
    )
    print(f"Motor: {sonuc['motor_grubu']}")
    print(f"Değer: {sonuc['deger_araligi']}")
    print(f"Yaş: {sonuc['yas_grubu']}")
    print(f"MTV: {sonuc['mtv_formatted']}")
    
    # Örnek 4: Elektrikli - Togg T10X (150 kW, 1.500.000 TL, 2 yaşında)
    print("\n--- Örnek 4: Togg T10X (150 kW) ---")
    sonuc = hesapla_mtv(
        motor_gucu_kw=150,
        tasit_degeri_tl=1500000,
        arac_yasi=2,
        yakit_tipi="elektrik"
    )
    print(f"Motor: {sonuc['motor_grubu']}")
    print(f"Değer: {sonuc['deger_araligi']}")
    print(f"Yaş: {sonuc['yas_grubu']}")
    print(f"MTV: {sonuc['mtv_formatted']}")
    
    # Örnek 5: Elektrikli - BYD Atto 3 (150 kW, 900.000 TL, 3 yaşında)
    print("\n--- Örnek 5: BYD Atto 3 (150 kW) ---")
    sonuc = hesapla_mtv(
        motor_gucu_kw=150,
        tasit_degeri_tl=900000,
        arac_yasi=3,
        yakit_tipi="elektrik"
    )
    print(f"Motor: {sonuc['motor_grubu']}")
    print(f"Değer: {sonuc['deger_araligi']}")
    print(f"Yaş: {sonuc['yas_grubu']}")
    print(f"MTV: {sonuc['mtv_formatted']}")
