"""Hourly LEIS system balance, matching the project's MATLAB reference."""
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class Config:
    modules: int = 2
    q0: float = 80
    initial_soc: float = 100
    air: float = 20
    charge: float = 20
    target: float = 80
    threshold: float = 20
    addon: float = 0
    auxiliary: float = 0
    horizon: int = 24

def normalize(raw, mapping, timezone='UTC', price_unit='€/MWh'):
    d = pd.DataFrame({k: raw[v] for k,v in mapping.items() if v != '—'})
    for k in ['timestamp','T_Aussen_C','Preis_EUR_MWh']:
        if k not in d: raise ValueError(f'Spalte fehlt: {k}')
    t = pd.to_datetime(d.timestamp, errors='raise', format='mixed', dayfirst=False)
    if t.dt.tz is None: t = t.dt.tz_localize(timezone, ambiguous='raise', nonexistent='raise')
    d['timestamp'] = t.dt.tz_convert('UTC')
    for k in d.columns.drop('timestamp'):
        d[k] = pd.to_numeric(d[k].astype(str).str.replace(',','.',regex=False), errors='raise')
        if not np.isfinite(d[k]).all(): raise ValueError(f'Fehlende/unendliche Werte in {k}.')
    if len(d)<2 or not d.timestamp.diff().iloc[1:].eq(pd.Timedelta(hours=1)).all():
        raise ValueError('Erwartet werden mindestens zwei lückenlose, chronologische Stundenwerte ohne Duplikate. Sommerzeit: UTC oder Zeitstempel mit Offset verwenden.')
    if price_unit=='€/kWh': d['Preis_EUR_MWh'] *= 1000
    d.attrs['heat_source'] = 'Importierte Gebäudelast' if 'Q_K_kW' in d else 'Modelllast: 2 × max(18 − T, 0) + 2 kW'
    if 'Q_K_kW' not in d: d['Q_K_kW'] = 2*np.maximum(18-d.T_Aussen_C,0)+2
    if (d.Q_K_kW<0).any(): raise ValueError('Gebäudelast darf nicht negativ sein.')
    return d.reset_index(drop=True)

def simulate(d, c=Config(), strategy='Referenz'):
    cap=1500*c.modules; e=cap*c.initial_soc/100; rows=[]
    t=d.T_Aussen_C.to_numpy(); p=d.Preis_EUR_MWh.to_numpy()/1000+c.addon
    load=d.Q_K_kW.to_numpy()
    def demand(temp, heat):
        cop=np.clip(.45*313.15/np.maximum(10,40-np.where(temp<=0,-5,temp-5)),2,6)
        return np.minimum(heat,c.q0)*(1-1/cop),cop
    request,cop=demand(t,load)
    def step(en,tt,rr):
        source=min(rr,40*c.modules,max(en,0)) if tt<=0 else rr
        en-=source if tt<=0 else 0
        air=min(c.air*c.modules,cap-en) if tt>3 else 0
        return en+air,source,air
    def future(en,tt,rr,ll,pp):
        value=0; missing=0
        for a,b,heat,price in zip(tt,rr,ll,pp):
            en,source,_=step(en,a,b); value+=(heat-source)*price; missing+=b-source
        return value,missing
    for i in range(len(d)):
        start=e; e,source,air=step(e,t[i],request[i]); charge=0
        maximum=min(c.charge*c.modules,max(0,cap*c.target/100-e))
        if strategy=='Preisregelung' and d.Preis_EUR_MWh.iloc[i]<=c.threshold: charge=maximum
        if strategy in ['Bedarf (kausal)','Ideale Prognose','Robuste Bedarfregelung'] and maximum>0:
            n=min(c.horizon,len(d)-i-1)
            if n:
                if strategy=='Ideale Prognose': tf=t[i+1:i+1+n]; pf=p[i+1:i+1+n]; lf=load[i+1:i+1+n]
                else:
                    tf=np.full(n,t[i]); indices=np.maximum(0,i+1+np.arange(n)-24*(1+np.arange(n)//24)); pf=p[indices]
                    # Repeat known daily heat profile for imported loads; formula for model loads.
                    lf=load[indices] if d.attrs.get('heat_source')=='Importierte Gebäudelast' else 2*np.maximum(18-tf,0)+2
                scenarios=[tf] if strategy!='Robuste Bedarfregelung' else [tf-2,tf,tf+2]
                prepared=[]
                for ts in scenarios:
                    ls=lf if d.attrs.get('heat_source')=='Importierte Gebäudelast' else 2*np.maximum(18-ts,0)+2
                    rs,_=demand(ts,ls); base,miss=future(e,ts,rs,ls,pf); prepared.append((ts,rs,base,miss,ls))
                best=.01
                for candidate in np.unique(np.r_[np.arange(0,maximum,5),maximum,min(maximum,prepared[0][3])]):
                    gains=[]
                    for ts,rs,base,miss,ls in prepared:
                        val,newmiss=future(e+candidate,ts,rs,ls,pf)
                        gains.append(base-val-candidate*p[i] if newmiss<miss-1e-8 else -np.inf)
                    if min(gains)>best: best=min(gains); charge=candidate
        e+=charge
        wp_el=source/(cop[i]-1); heat=source+wp_el; heater=max(0,load[i]-heat)
        pel=wp_el+heater+charge+c.auxiliary
        rows.append([start,e,source,air,charge,cop[i],heat,heater,pel,request[i]-source,(cap-e)*3600/333])
    r=d.copy()
    names=['E_Start_kWh','E_Ende_kWh','Q_Quelle_kW','Q_Luftregen_kW','P_Regeneration_kW','COP','Q_WP_kW','Heizstab_kW','P_el_kW','Quellendefizit_kW','Eismasse_kg']
    r[names]=np.array(rows); r['SOC_%']=100*r.E_Ende_kWh/cap
    r['SOC_Start_%']=100*r.E_Start_kWh/cap
    r['Kosten_EUR']=r.P_el_kW*p; r['Modus']=np.where(t<=0,'Eisspeicher','Direktluft')
    assert np.allclose(r.E_Ende_kWh-r.E_Start_kWh,-np.where(t<=0,r.Q_Quelle_kW,0)+r.Q_Luftregen_kW+r.P_Regeneration_kW)
    assert np.allclose(r.Q_WP_kW+r.Heizstab_kW,load)
    return r

def metrics(r):
    return {'Stromkosten [€]':r.Kosten_EUR.sum(),'Strom [kWh]':r.P_el_kW.sum(),
            'System-Arbeitszahl':r.Q_K_kW.sum()/r.P_el_kW.sum() if r.P_el_kW.sum()>0 else np.nan,
            'Heizstab [kWh]':r.Heizstab_kW.sum(),'Min. SOC [%]':min(r['SOC_%'].min(),r['SOC_Start_%'].min()),
            'Quellendefizit [kWh]':r.Quellendefizit_kW.sum(),'Endenergie [kWh]':r.E_Ende_kWh.iloc[-1],
            'Zusatzladung [kWh]':r.P_Regeneration_kW.sum()}
