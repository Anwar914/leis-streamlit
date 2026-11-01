"""Teaching view using the same energy engine as the annual simulation."""
from dataclasses import replace
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from leis_engine import Config, simulate, metrics

def system_picture(row):
    """Schematic inspired by the supplied HTML; values come from Python balance."""
    source=float(row.Q_Quelle_kW); ice=row.Modus=='Eisspeicher'
    def line(path,color,active,label,x,y):
        css='leisflow' if active else ''
        return f'<path d="{path}" stroke="{color if active else "#475569"}" stroke-width="5" fill="none" class="{css}"/><text x="{x}" y="{y}" fill="{color}" font-size="14">{label}</text>'
    def box(x,y,w,h,title,subtitle,color):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#1e293b" stroke="{color}" stroke-width="2"/><text x="{x+12}" y="{y+28}" fill="#f8fafc" font-size="17">{title}</text><text x="{x+12}" y="{y+53}" fill="{color}" font-size="14">{subtitle}</text>'
    wp_el=source/(row.COP-1)
    svg='<svg viewBox="0 0 920 510" width="100%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Energieflüsse im Luft-Eisspeichersystem">'
    svg+='<rect width="920" height="510" rx="16" fill="#0f172a"/>'
    svg+=box(30,30,235,80,'Luftmodul',f'{row.T_Aussen_C:.1f} °C Außenluft','#fbbf24')
    svg+=box(30,235,235,205,'Wasser-/Eisspeicher',f'SOC {row["SOC_Start_%"]:.1f} → {row["SOC_%"]:.1f} %','#38bdf8')
    ice_height=(100-row['SOC_%'])*.8
    svg+=f'<rect x="45" y="307" width="205" height="80" fill="#087e8b"/><rect x="45" y="{387-ice_height}" width="205" height="{ice_height}" fill="#bae6fd"/><text x="45" y="416" fill="#e2e8f0" font-size="13">Eisanteil am Stundenende (Schema)</text>'
    svg+=box(420,170,215,100,'Wärmepumpe',f'COP-Modell {row.COP:.2f}','#a78bfa')
    svg+=box(705,170,190,100,'Gebäude',f'Bedarf {row.Q_K_kW:.1f} kW','#fb7185')
    svg+=box(705,365,190,80,'Gebäude-Heizstab',f'{row.Heizstab_kW:.1f} kW Strom','#fb923c')
    svg+=line('M265 70 H345 V195 H420','#fbbf24',not ice and source>0,f'{source if not ice else 0:.1f} kW Quelle',280,140)
    svg+=line('M265 335 H345 V245 H420','#38bdf8',ice and source>0,f'{source if ice else 0:.1f} kW Quelle',280,365)
    svg+=line('M635 220 H705','#fb7185',row.Q_WP_kW>0,f'{row.Q_WP_kW:.1f} kW',638,200)
    svg+=line('M800 365 V270','#fb923c',row.Heizstab_kW>0,f'{row.Heizstab_kW:.1f} kW',815,322)
    svg+=line('M110 110 V235','#34d399',row.Q_Luftregen_kW>0,f'Auftauen {row.Q_Luftregen_kW:.1f} kW',35,165)
    svg+=line('M525 405 V270','#c4b5fd',wp_el>0,f'Verdichterstrom {wp_el:.1f} kW',395,435)
    svg+=line('M145 485 V440','#fda4af',row.P_Regeneration_kW>0,f'Zusatzladung {row.P_Regeneration_kW:.1f} kW Strom',35,475)
    return '<style>.leisflow{stroke-dasharray:9 5;animation:leisflow 1.5s linear infinite}@keyframes leisflow{to{stroke-dashoffset:-28}}@media(prefers-reduced-motion:reduce){.leisflow{animation:none}}</style>'+svg+'</svg>'

def render(config,data,calculate):
    st.subheader('Parameter ausprobieren · Was passiert wo?')
    st.write('Verfolge die Wärme von der Quelle bis zum Gebäude. Farbige, bewegte Leitungen zeigen aktive Energieflüsse; graue Leitungen sind inaktiv.')
    mode=st.radio('Versuch wählen',['Was passiert, wenn …?','Stunde aus dem Datenverlauf'],horizontal=True,key='ex_mode')
    if mode=='Was passiert, wenn …?':
        preset=st.selectbox('Ausgangssituation',['Frost','Milder Tag / Auftauen','Leerer Speicher','Hohe Heizlast'],key='ex_preset')
        defaults={'Frost':(-5.,50.,50),'Milder Tag / Auftauen':(7.,25.,30),'Leerer Speicher':(-8.,55.,0),'Hohe Heizlast':(-10.,120.,50)}
        temp,load,soc=defaults[preset]
        a,b,c=st.columns(3)
        with a: temp=st.slider('Außentemperatur im Versuch [°C]',-20.,35.,temp,.5,key='ex_temp_'+preset)
        with b: load=st.slider('Gebäude-Heizlast im Versuch [kW]',0.,200.,load,1.,key='ex_load_'+preset)
        with c: soc=st.slider('Anfangs-SOC im Versuch [%]',0,100,soc,key='ex_soc_'+preset)
        duration=st.select_slider('Versuchsdauer [h]',options=[1,6,24,48,168],value=24,key='ex_duration')
        price=st.number_input('Strompreis im Versuch [€/MWh]',value=80.,key='ex_price')
        control=st.selectbox('Zusatzladung',['Referenz','Preisregelung'],key='ex_strategy')
        d=pd.DataFrame({'timestamp':pd.date_range('2025-01-01',periods=duration,freq='h',tz='UTC'),'T_Aussen_C':temp,'Q_K_kW':load,'Preis_EUR_MWh':price})
        cfg=replace(config,initial_soc=soc)
        st.caption('Lernversuch mit konstanten, frei gewählten Bedingungen; keine Wetterprognose. Module, WP-Leistung, Regenerationsleistung und Tarif aus der Seitenleiste. Der Anfangs-SOC oben gilt für diesen Versuch.')
        result=calculate(d,cfg,control)
        # Same conditions and initial SOC isolate the effect of configuration/control.
        basecfg=replace(Config(),initial_soc=soc,addon=cfg.addon,auxiliary=cfg.auxiliary)
        reference=calculate(d,basecfg,'Referenz')
    else:
        control=st.selectbox('Regelung des Datenverlaufs',['Referenz','Preisregelung'],key='ex_history_strategy')
        result=calculate(data,config,control); reference=None; cfg=config
        st.caption('Zustand aus der vollständigen Simulation des gewählten Zeitraums. Der Speicher wird beim Auswählen einer Stunde nicht zurückgesetzt.')
    i=st.slider('Angezeigte Stunde',0,len(result)-1,0,key='ex_hour') if len(result)>1 else 0
    row=result.iloc[i]
    st.html(system_picture(row))
    st.caption(f'{row.timestamp} · Leistungen sind Stundenmittel. Speicherbild am Stundenende; keine räumliche Eisfront oder hydraulische Rohrplanung. Luftregeneration ist ohne zusätzliche Stromaufnahme modelliert; Hilfsenergie separat einstellbar.')
    source=float(row.Q_Quelle_kW); wp_el=source/(row.COP-1)
    with st.container(horizontal=True):
        st.metric('Aktive Quelle',row.Modus,border=True)
        st.metric('Gesamtstrom',f'{row.P_el_kW:.2f} kW',border=True)
        st.metric('Stromkosten dieser Stunde',f'{row.Kosten_EUR:.2f} €',border=True)
        st.metric('Quellendefizit',f'{row.Quellendefizit_kW:.2f} kW',border=True)
    st.write(f'**Wärmepumpe:** {source:.2f} kW Quellenwärme + {wp_el:.2f} kW Verdichterstrom = {row.Q_WP_kW:.2f} kW Heizwärme.')
    st.write(f'**Gebäude:** {row.Q_WP_kW:.2f} kW Wärmepumpe + {row.Heizstab_kW:.2f} kW Heizstab = {row.Q_K_kW:.2f} kW Bedarf.')
    if row.Modus=='Eisspeicher':
        st.info(f'Bei {row.T_Aussen_C:.1f} °C wird der Speicher genutzt. Entzug ist auf {40*cfg.modules:.0f} kW und den Energieinhalt begrenzt. Der COP ist eine Modellkennzahl; bei leerem Speicher liefert die Wärmepumpe trotz angezeigtem COP keine Wärme.')
    elif row.T_Aussen_C>3:
        st.info('Die Luft versorgt die Wärmepumpe und kann vorhandenes Eis auftauen. Ein voller Speicher nimmt keine weitere latente Energie auf.')
    else: st.info('Direktluftbetrieb: Oberhalb 0 °C wird Luft genutzt. Die Regeneration bleibt bis einschließlich 3 °C aus.')
    if row.Heizstab_kW>1e-8: st.warning('Der Gebäude-Heizstab deckt die Restlast. Ursache kann eine begrenzte WP-Leistung, Quellenleistung oder ein leerer Speicher sein. Dadurch bleibt das Gebäude versorgt, aber der Strombedarf steigt.')
    component=st.selectbox('Bauteil genauer erklären',['Luftmodul','Eisspeicher','Wärmepumpe','Gebäude-Heizstab','Elektrische Regeneration','Strompreis'],key='ex_component')
    explanations={
        'Luftmodul':'Überträgt Wärme aus der Außenluft. Im Projektmodell gilt: Direktbetrieb oberhalb 0 °C, Speicherregeneration oberhalb 3 °C. Die Luftquelle hat hier keine Leistungsgrenze; die WP-Leistung bleibt begrenzt.',
        'Eisspeicher':'Beim Gefrieren wird latente Wärme entzogen und der SOC sinkt. Beim Auftauen steigt er. Mehr Module vergrößern Kapazität und maximale Quellenleistung; die physikalische Kapazität eines Moduls steigt durch häufigeres Laden nicht.',
        'Wärmepumpe':'Der Verdichter hebt das Temperaturniveau. Heizwärme = Quellenwärme + Verdichterstrom. Q₀ begrenzt die Heizleistung, nicht die Quellenleistung. Der COP ist eine Carnot-Näherung, keine gemessene Kennlinie.',
        'Gebäude-Heizstab':'Versorgt das Gebäude direkt mit elektrischer Wärme (Wirkungsgrad 1). Er regeneriert den Speicher nicht und hat in diesem Modell keine Leistungsgrenze.',
        'Elektrische Regeneration':'Ein separater elektrischer Wärmeeintrag taut Eis auf. Bei Preisregelung wird nur unter der Preisgrenze und bis zum Ziel-SOC geladen. Diese Energie steht erst in der folgenden Stunde zur Verfügung und wird vollständig als Strom bilanziert.',
        'Strompreis':'Ändert die Kosten, nicht automatisch den physikalischen COP. Im Referenzbetrieb hat der Preis keinen Einfluss auf die Schaltung. Bei Preisregelung beeinflusst er die elektrische Zusatzladung.'}
    st.write(explanations[component])
    fig=px.line(result,x='timestamp',y=['SOC_%','SOC_Start_%'],labels={'value':'SOC [%]','timestamp':'Zeit (UTC)'},title='Speicherentwicklung im Versuch')
    st.plotly_chart(fig,width='stretch')
    if reference is not None:
        st.subheader('Was hat die Änderung bewirkt?')
        st.caption('Vergleich: gleiche Temperatur, Last, Dauer, Anfangs-SOC und Tarif. Ausgangsanlage: 2 Module, 80 kW WP, 20 kW Luftregeneration je Modul, keine elektrische Zusatzladung.')
        before=metrics(reference); after=metrics(result)
        keys=['Strom [kWh]','Stromkosten [€]','Heizstab [kWh]','Endenergie [kWh]','Quellendefizit [kWh]']
        table=pd.DataFrame({'Kennzahl':keys,'Ausgangsanlage':[before[k] for k in keys],'Aktuelle Einstellung':[after[k] for k in keys],'Änderung':[after[k]-before[k] for k in keys]})
        st.dataframe(table,hide_index=True)
        st.caption('Dies ist eine Ursachenanalyse, keine Wirtschaftlichkeitsbewertung. Unterschiedliche Modulzahlen verändern auch Anfangsenergie und Endbestand. Bei Frost kann mehr Speicher den Heizstab verringern; eine größere WP hilft nur bei ausreichender Quelle.')
    st.download_button('Versuch als CSV herunterladen',result.to_csv(index=False).encode('utf-8-sig'),'LEIS_systemversuch.csv','text/csv',on_click='ignore')
