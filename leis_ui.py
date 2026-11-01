"""Interactive project dashboard; all computations run locally."""
from pathlib import Path
from dataclasses import asdict, replace
import io, json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from leis_engine import Config, normalize, simulate, metrics

ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'leis_assets'
STRATEGIES=['Referenz','Preisregelung','Bedarf (kausal)','Ideale Prognose','Robuste Bedarfregelung']
st.set_page_config(page_title='LEIS · Gruppe 1',page_icon=':material/ac_unit:',layout='wide')
st.title('LEIS · Energie verstehen, Betrieb vergleichen')
st.caption('Luft-Eisspeicher LE3 · stündliche Systemsimulation')

@st.cache_data(max_entries=24,show_spinner='Energiebilanz wird berechnet …')
def calculate(data,config,strategy):
    return simulate(data,config,strategy)

def download(data,name,label='CSV herunterladen'):
    st.download_button(label,data.to_csv(index=False).encode('utf-8-sig'),name,'text/csv',key=name,on_click='ignore')

def plot(data,columns,title,unit):
    fig=px.line(data,x='timestamp',y=columns,title=title,labels={'value':unit,'timestamp':'Zeit (UTC)','variable':'Signal'})
    fig.update_layout(hovermode='x unified',legend=dict(orientation='h',y=-.25))
    st.plotly_chart(fig,width='stretch')

with st.sidebar:
    st.subheader('Arbeitsbereich')
    page=st.radio('Ansicht',['Startseite','Simulation','Regelungsvergleich','Parametervarianten','SOC-Schätzung','Projektergebnisse & Modell'],key='page')
    source=st.radio('Datengrundlage',['Projekt Nürnberg 2025','Eigene Daten'],key='source')
    modules=st.number_input('LE3-Module',1,20,2,key='modules')
    q0=st.number_input('WP-Nennwärmeleistung [kW]',1.,1000.,80.,key='q0')
    initial=st.slider('Anfangs-SOC [%]',0,100,100)
    with st.expander('Regeneration & Stromtarif'):
        air=st.number_input('Luftregeneration [kW/Modul]',0.,100.,20.)
        charge=st.number_input('Elektrische Regeneration [kW/Modul]',0.,100.,20.)
        target=st.slider('Ziel-SOC für Zusatzladung [%]',0,100,80)
        limit=st.number_input('Preisgrenze [€/MWh]',value=20.)
        addon=st.number_input('Arbeitspreis-Aufschlag [€/kWh]',0.,2.,0.,.01)
        aux=st.number_input('Konstante Hilfsleistung [kW]',0.,50.,0.,.1)
        horizon=st.selectbox('Prognosehorizont [h]',[24,48])
    st.caption('1500 kWh latent und 40 kW Quellenentzug je Modul. Heizstab am Gebäude deckt die Restlast ohne Leistungsgrenze.')
c=Config(modules,q0,initial,air,charge,target,limit,addon,aux,horizon)

if source=='Projekt Nürnberg 2025':
    raw=pd.read_csv(ROOT/'leis_inputs_2025.csv')
    data=normalize(raw,{k:k for k in raw.columns})
    st.caption('DWD Station 03668 · SMARD DE/LU · lokales Kalenderjahr 2025 · keine Live-Messverbindung')
else:
    st.subheader('Eigene Stundenwerte bewerten')
    st.write('CSV oder XLSX mit Zeit, Außentemperatur und Strompreis. Gebäudelast optional; sonst wird die Projekt-Modelllast berechnet.')
    template=pd.DataFrame({'timestamp':['2025-01-01 00:00:00','2025-01-01 01:00:00'],'T_Aussen_C':[-5,-4],'Preis_EUR_MWh':[80,70],'Q_K_kW':[48,46]})
    download(template,'LEIS_importvorlage.csv','Importvorlage herunterladen')
    uploaded=st.file_uploader('Eingabedaten',type=['csv','xlsx'])
    if uploaded is None: st.info('Datei auswählen, um die eigene Simulation zu starten.'); st.stop()
    with st.expander('Importeinstellungen',expanded=True):
        tz=st.selectbox('Zeitzone bei Zeitstempeln ohne Offset',['UTC','Europe/Berlin'])
        unit=st.selectbox('Preiseinheit',['€/MWh','€/kWh'])
        header=st.number_input('Zeile mit Spaltennamen (1-basiert)',1,100,1)
        decimal=st.selectbox('Dezimaltrennzeichen',['.',','])
        try:
            if uploaded.name.endswith('.xlsx'):
                book=pd.ExcelFile(io.BytesIO(uploaded.getvalue()))
                sheet=st.selectbox('Tabellenblatt',book.sheet_names)
                raw=pd.read_excel(book,sheet_name=sheet,header=header-1,decimal=decimal)
            else:
                encoding=st.selectbox('Zeichensatz',['utf-8-sig','cp1252'])
                raw=pd.read_csv(io.BytesIO(uploaded.getvalue()),sep=None,engine='python',encoding=encoding,header=header-1,decimal=decimal)
            mapping={}
            for name in ['timestamp','T_Aussen_C','Preis_EUR_MWh','Q_K_kW']:
                options=['—']+list(raw.columns)
                mapping[name]=st.selectbox(name,options,index=options.index(name) if name in options else 0)
            data=normalize(raw,mapping,tz,unit)
        except Exception as exc: st.error(f'Import bitte prüfen: {exc}'); st.stop()

st.caption(f'{len(data):,} Stunden · {data.attrs["heat_source"]} · Zeitanzeige UTC')
with st.expander('Zeitraum & Eingabedaten'):
    dates=st.date_input('Simulationszeitraum (UTC)',(data.timestamp.iloc[0].date(),data.timestamp.iloc[-1].date()),key='dates_'+source)
    if len(dates)==2:
        attrs=data.attrs.copy()
        data=data[(data.timestamp.dt.date>=dates[0])&(data.timestamp.dt.date<=dates[1])].reset_index(drop=True)
        data.attrs=attrs
    st.dataframe(data.head(48),hide_index=True)
    download(data,'LEIS_eingabedaten.csv')
if data.empty: st.error('Der gewählte Zeitraum enthält keine Daten.'); st.stop()

if page=='Startseite':
    from leis_explainer import render
    overview,experiment=st.tabs(['Systemübersicht','Parameter ausprobieren'])
    with overview:
        st.caption('Interaktive Lernansicht: animierte Demonstrationswerte, keine Messdaten. Solarabsorber, Puffer und Flächenheizung sind hier schematische Ergänzungen; sie werden im LE3-Jahresmodell nicht separat simuliert.')
        st.iframe(ASSETS/'startseite_reviewed.html',height='content',alt='Interaktive Eisspeicheranlage mit anklickbaren Komponenten')
    with experiment:
        render(c,data,calculate)
elif page=='Simulation':
    strategy=st.selectbox('Regelung',STRATEGIES)
    if strategy=='Ideale Prognose': st.warning('Rückblickender Vergleich mit bekannter Zukunft. Kein real ausführbarer Regler.')
    if strategy=='Robuste Bedarfregelung': st.info('Experiment: Laden nur bei Vorteil in drei Temperaturszenarien (−2 / 0 / +2 K). Keine nachgewiesene Robustheitsgarantie.')
    r=calculate(data,c,strategy); m=metrics(r)
    with st.container(horizontal=True):
        for key in ['Stromkosten [€]','Strom [kWh]','System-Arbeitszahl','Min. SOC [%]']: st.metric(key,f'{m[key]:,.2f}',border=True)
    st.caption('Arbeitszahl gilt für den gewählten Zeitraum; nur beim vollständigen Jahr als JAZ interpretieren. Zusatzladung und Hilfsenergie sind enthalten.')
    a,b=st.columns(2)
    with a: plot(r,['Q_K_kW','Q_WP_kW','Heizstab_kW'],'Gebäude versorgen','Leistung [kW]')
    with b: plot(r,['SOC_%'],'Ladezustand am Stundenende','SOC [%]')
    plot(r,['Q_Quelle_kW','Q_Luftregen_kW','P_Regeneration_kW','Quellendefizit_kW'],'Quellen und Regeneration','Leistung [kW]')
    st.subheader('Speicher im Zeitverlauf')
    st.caption('Schematische Eisanteile, keine räumliche Eisfront. 100 % SOC = aktives Wasser bei 0 °C.')
    play=st.toggle('Animation abspielen')
    speed=st.select_slider('Stunden je Bild',options=[1,6,24,168],value=24)
    start=st.slider('Stunde auswählen',0,len(r)-1,0) if len(r)>1 else 0
    if st.session_state.get('anim_start')!=start: st.session_state.anim_index=start; st.session_state.anim_start=start
    @st.fragment(run_every=1 if play else None)
    def animate():
        idx=min(st.session_state.get('anim_index',start),len(r)-1); row=r.iloc[idx]
        left,right=st.columns([1,2])
        with left:
            fig=go.Figure([go.Bar(x=['Speicher'],y=[100-row['SOC_%']],name='Eis',marker_color='#b9e5f2'),go.Bar(x=['Speicher'],y=[row['SOC_%']],name='Wasser',marker_color='#087e8b')])
            fig.update_layout(barmode='stack',height=260,yaxis=dict(range=[0,100],title='Aktiver Anteil [%]'))
            st.plotly_chart(fig,width='stretch')
        with right:
            st.write(str(row.timestamp)); st.metric('SOC',f'{row["SOC_%"]:.1f} %')
            st.write(f'{row.Modus} · {row.T_Aussen_C:.1f} °C · {row.Preis_EUR_MWh:.2f} €/MWh')
            st.write(f'Eismassenäquivalent: {row.Eismasse_kg:,.0f} kg · Heizstab: {row.Heizstab_kW:.1f} kW')
        if play: st.session_state.anim_index=(idx+speed)%len(r)
    animate()
    plot(r,['T_Aussen_C'],'Außentemperatur','Temperatur [°C]')
    plot(r,['Preis_EUR_MWh'],'Börsenstrompreis','Preis [€/MWh]')
    download(r,'LEIS_simulation.csv','Alle Simulationsergebnisse herunterladen')
    st.download_button('Parameter herunterladen',json.dumps(asdict(c),indent=2),'LEIS_parameter.json','application/json')

elif page=='Regelungsvergleich':
    st.subheader('Regelungen mit denselben Eingaben vergleichen')
    selected=st.multiselect('Varianten',STRATEGIES,default=['Referenz','Preisregelung','Bedarf (kausal)'])
    st.caption('Kausal: aktuelle Temperatur konstant, Preise und importierte Last aus dem zuletzt bekannten Tagesverlauf. Ideal: tatsächliche Zukunft. Robust: zusätzliche ±2-K-Szenarien.')
    if st.button('Vergleich berechnen',type='primary'):
        results={s:calculate(data,c,s) for s in dict.fromkeys(['Referenz']+selected)}
        table=pd.DataFrame([dict(Regelung=s,**metrics(r)) for s,r in results.items()]); ref=table.iloc[0]
        table['Endbestand gleich']=np.isclose(table['Endenergie [kWh]'],ref['Endenergie [kWh]'],atol=1e-6)
        table['Vergleichbare Einsparung [€]']=np.where(table['Endbestand gleich'],ref['Stromkosten [€]']-table['Stromkosten [€]'],np.nan)
        st.dataframe(table,hide_index=True)
        st.plotly_chart(px.bar(table,x='Regelung',y='Stromkosten [€]',color='Regelung'),width='stretch')
        st.warning('Bei ungleichem Endbestand wird keine vergleichbare Einsparung ausgewiesen. Niedrigere Rohkosten allein belegen dann keinen Vorteil. Keine Investitionsrechnung enthalten.')
        download(table,'LEIS_regelungsvergleich.csv')

elif page=='Parametervarianten':
    st.subheader('Speicher- und Wärmepumpengröße untersuchen')
    ns=st.multiselect('Modulzahlen',[1,2,3,4,6,8],default=[1,2,4])
    qs=st.multiselect('Wärmepumpenleistungen [kW]',[20,40,60,80,100,120],default=[40,80])
    if st.button('Varianten berechnen',type='primary'):
        table=pd.DataFrame([dict(Module=n,WP_kW=q,**metrics(calculate(data,replace(c,modules=n,q0=q),'Referenz'))) for n in ns for q in qs])
        if not table.empty:
            st.dataframe(table,hide_index=True)
            st.plotly_chart(px.scatter(table,x='Stromkosten [€]',y='System-Arbeitszahl',color='Module',size='WP_kW',hover_data=table.columns),width='stretch')
            st.caption('Betriebsergebnisse ohne Investitionskosten. Unterschiedliche Kapazitäten und Endbestände beachten.')
            download(table,'LEIS_varianten.csv')

elif page=='SOC-Schätzung':
    st.subheader('SOC aus Solemessungen schätzen')
    st.write('Nur Speicherzweig: Q = ρ · cₚ · V̇ / 3600 · (T_aus − T_ein). Positiv = Wärmeentzug. Externe Wärme separat, nicht doppelt zählen.')
    sample=pd.DataFrame({'timestamp':['2025-01-01 00:00:00','2025-01-01 01:00:00'],'Vdot_m3_h':[5,5],'T_in_C':[-4,-4],'T_out_C':[0,0],'Q_ext_kW':[0,0]})
    download(sample,'LEIS_sensorvorlage.csv','Sensorvorlage herunterladen')
    f=st.file_uploader('Stündliche Sensordaten (CSV gemäß Vorlage)',type='csv')
    a,b=st.columns(2)
    with a:
        rho=st.number_input('Soledichte [kg/m³]',500.,2000.,1030.)
        cp=st.number_input('Wärmekapazität Sole [kJ/(kg K)]',.1,10.,3.8)
        dv=st.number_input('Volumenstrom-Fehlergrenze [m³/h]',0.,10.,.02)
    with b:
        dt=st.number_input('Temperatur-Fehlergrenze je Sensor [K]',0.,10.,.1)
        uncertainty=st.number_input('Anfangs-Energieunsicherheit [kWh]',0.,30000.,0.)
        dq=st.number_input('Fehlergrenze externe Wärme [kW]',0.,100.,0.)
    if f:
        try:
            s=pd.read_csv(f,sep=None,engine='python'); dates=pd.to_datetime(s.timestamp,utc=True)
            if s.empty or dates.isna().any() or not dates.diff().iloc[1:].eq(pd.Timedelta(hours=1)).all(): raise ValueError('Stündliche lückenlose UTC-Zeitachse erforderlich.')
            vals=s[['Vdot_m3_h','T_in_C','T_out_C','Q_ext_kW']].apply(pd.to_numeric,errors='raise')
            if not np.isfinite(vals.to_numpy()).all() or (vals.Vdot_m3_h<0).any(): raise ValueError('Ungültige Messwerte.')
            cap=1500*modules; e=cap*initial/100; u=uncertainty; rows=[]
            for v,ti,to,qe in vals.itertuples(index=False,name=None):
                q=rho*cp*v*(to-ti)/3600; unbounded=e-q+qe; e=np.clip(unbounded,0,cap)
                u+=rho*cp/3600*(dv*abs(to-ti)+(v+dv)*2*dt)+dq
                rows.append([e/cap*100,max(0,e-u)/cap*100,min(cap,e+u)/cap*100,unbounded-e,q])
            out=pd.DataFrame(rows,columns=['SOC-Schätzung','Untergrenze','Obergrenze','Bilanzrest_kWh','Q_Entzug_kW']); out['timestamp']=dates
            plot(out,['SOC-Schätzung','Untergrenze','Obergrenze'],'Bilanzschätzung mit Fehlergrenzen','SOC [%]')
            st.caption('Konservative Fehlergrenzen, kein Konfidenzintervall. Dichte/Wärmekapazität als konstant und exakt angenommen. Keine unabhängige Validierung. Bilanzrest zeigt Kapazitätsüberschreitungen.')
            download(out,'LEIS_soc_schaetzung.csv')
        except Exception as exc: st.error(f'Sensordaten prüfen: {exc}')

else:
    st.subheader('Dokumentierte MATLAB-Ergebnisse')
    st.info('Archivierte Läufe: Nürnberg 2025, 2 Module, Q₀ = 80 kW, Modelllast. Diese Tabellen ändern sich nicht mit den aktuellen Sidebar-Parametern.')
    choice=st.selectbox('Ergebnisdatei',['robustheit_2025.csv','regelungsvergleich_2025.csv','prognosevergleich_2025.csv','variantenvergleich_2025.csv','jahreskennzahlen_2025.csv'])
    archive=pd.read_csv(ASSETS/choice); st.dataframe(archive,hide_index=True); download(archive,choice)
    if choice=='robustheit_2025.csv': st.caption('Nachlauf: 95 gemeinsame Stunden mit wiederholtem Jahresanfang 2025 bis zum Bestandsausgleich. Keine gemessenen 2026-Daten. Negative Einsparung = Mehrkosten.')
    st.subheader('Das System im Modell')
    for col,file,title in zip(st.columns(4),['brochure_p04_7.png','brochure_p04_2.png','brochure_p15_3.png','brochure_p15_2.png'],['Luftmodul','Eisspeicher','Wärmepumpe','Gebäude']):
        with col:
            if (ASSETS/file).exists(): st.image(str(ASSETS/file),caption=title,width='stretch')

    if (ASSETS/'modelluebersicht.png').exists(): st.image(str(ASSETS/'modelluebersicht.png'),caption='Vorhandenes Simulink-Systemmodell',width='stretch')
    st.markdown('''**Modellgrenzen:** Latent 1500 kWh/Modul. Sensible 700 kWh werden nicht addiert. Eismassenäquivalent aus 333 kJ/kg, nicht das ganze Beckenvolumen. Luftquelle > 0 °C, Speicher ≤ 0 °C, Luftregeneration > 3 °C. COP: Carnot-Näherung mit Gütegrad 0,45, Kondensation 40 °C, Quellabstand 5 K, begrenzt auf 2–6. Keine Herstellerkennlinie, Eiswiderstände, Erdreichwärme oder Pumpenkennlinien. Nacht/Tag-Faktor v mangels definiertem Ladeprozess nicht aktiv; Ladeleistung direkt einstellbar. Heizstabwirkungsgrad 1. Keine Realdatenvalidierung des Speichers, kein Echtzeit-Digitalzwilling.''')
