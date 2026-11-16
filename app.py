"""International cost of capital — rates are decimals in the model, percentages in UI."""
import math
import re
from datetime import datetime, timezone
from io import BytesIO, StringIO
import pandas as pd
import requests
from bs4 import BeautifulSoup
from babel.numbers import get_territory_currencies
import pycountry
import streamlit as st

BETA = 'https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls'
BETA_HTML = 'https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html'
SPREAD = 'https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html'
OECD = 'https://sdmx.oecd.org/public/rest/data/OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,2.0/.A.CIT_C.ST..S13...?startPeriod=2024&dimensionAtObservation=AllDimensions'
OECD_PAGE = 'https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html'
BONDS = 'https://tradingeconomics.com/bonds'
DEFAULT = 'Software (System & Application)'
# Rounded, dated reference subset; never represented as a successful fetch.
SEED = {DEFAULT:1.23,'Advertising':.93,'Aerospace/Defense':.85,'Air Transport':.70,'Auto & Truck':1.27,'Green & Renewable Energy':.46,'Power':.31,'Semiconductor':1.49,'Software (Internet)':1.55,'Utility (Water)':.28}
ALIASES = {'United States':'United States','United Kingdom':'United Kingdom','South Korea':'Korea, Republic of','South Africa':'South Africa','Russia':'Russian Federation','Taiwan':'Taiwan, Province of China','Turkey':'Türkiye','Czech Republic':'Czechia','Vietnam':'Viet Nam','Hong Kong':'Hong Kong','Iran':'Iran, Islamic Republic of','Bolivia':'Bolivia, Plurinational State of','Venezuela':'Venezuela, Bolivarian Republic of'}
SLUGS = {'Türkiye':'turkey','Korea, Republic of':'south-korea','Taiwan, Province of China':'taiwan','Czechia':'czech-republic','Russian Federation':'russia','Viet Nam':'vietnam','United States':'united-states','United Kingdom':'united-kingdom','Hong Kong':'hong-kong','Slovakia':'slovakia'}

def calculate(beta, tax, debt, erp, us_yield, local_yield, us_spread, local_override=None, method='Parity'):
    if not 0 <= debt < 1 or not 0 <= tax <= 1 or min(us_yield,local_yield) <= -1:
        raise ValueError('Invalid debt, tax or government yield.')
    levered = beta * (1 + (1-tax)*debt/(1-debt))
    ke_us = us_yield + levered*erp
    kd_us = us_yield + us_spread
    factor = (1+local_yield)/(1+us_yield)
    auto = us_spread*factor if method == 'Parity' else us_spread
    spread = auto if local_override is None else local_override
    ke_local = (1+ke_us)*factor-1 if method == 'Parity' else local_yield+levered*erp
    kd_local = local_yield+spread
    return {'beta':levered,'auto_spread':auto,'spread':spread,'ke_us':ke_us,'kd_us':kd_us,'wacc_us':(1-debt)*ke_us+debt*kd_us*(1-tax),'ke_local':ke_local,'kd_local':kd_local,'wacc_local':(1-debt)*ke_local+debt*kd_local*(1-tax)}

def now(): return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
def get(url, **kwargs):
    headers={'User-Agent':'Mozilla/5.0 (compatible; academic-cost-of-capital-app)'}
    headers.update(kwargs.pop('headers',{}))
    r=requests.get(url,headers=headers,timeout=12,**kwargs); r.raise_for_status(); return r

def date_in(text):
    m=re.search(r'(?:as of|last updated(?: in| on)?)\s*[:]?\s*((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(?:\d{1,2},?\s+)?\d{4})',text,re.I)
    return m.group(1) if m else 'Not published / parsed'

def norm(x): return re.sub(r'\s+',' ',str(x)).strip().lower()
def parse_betas(frame):
    for i,row in frame.iterrows():
        names=[norm(v) for v in row]
        if 'industry name' in names and 'unlevered beta' in names:
            a,b=names.index('industry name'),names.index('unlevered beta')
            out={str(r.iloc[a]).strip():float(v) for _,r in frame.iloc[i+1:].iterrows() if pd.notna(r.iloc[a]) and not norm(r.iloc[a]).startswith('total market') and pd.notna(v:=pd.to_numeric(r.iloc[b],errors='coerce'))}
            if DEFAULT in out and len(out)>50: return out
    raise ValueError('Industry beta header or full dataset not found')

@st.cache_data(ttl=21600,show_spinner=False)
def fetch_betas():
    errors=[]
    try:
        r=get(BETA); sheets=pd.read_excel(BytesIO(r.content),sheet_name=None,header=None,engine='xlrd')
        for f in sheets.values():
            try:
                values=parse_betas(f); return values,date_in(' '.join(str(x) for x in f.iloc[:8].values.flatten())),BETA,now(),'Live workbook'
            except ValueError: continue
        raise ValueError('No matching workbook sheet')
    except Exception as e: errors.append(str(e))
    try:
        r=get(BETA_HTML); soup=BeautifulSoup(r.text,'html.parser')
        for f in pd.read_html(StringIO(r.text),header=None):
            try:
                if not isinstance(f.columns,pd.RangeIndex): f=pd.concat([pd.DataFrame([list(f.columns)]),f.set_axis(range(len(f.columns)),axis=1)],ignore_index=True)
                return parse_betas(f),date_in(soup.get_text(' ',strip=True)),BETA_HTML,now(),'Live HTML fallback'
            except ValueError: continue
        raise ValueError('No matching HTML table')
    except Exception as e: errors.append(str(e))
    return SEED,'January 2026',BETA_HTML,'Not fetched','Dated reference subset; '+ '; '.join(errors)

@st.cache_data(ttl=21600,show_spinner=False)
def fetch_spread():
    try:
        r=get(SPREAD); soup=BeautifulSoup(r.text,'html.parser')
        for tr in soup.find_all('tr'):
            cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])]
            for i,c in enumerate(cells[:-1]):
                if re.sub(r'\s','',c).upper()=='BAA2/BBB':
                    v=float(cells[i+1].replace('%','').strip()); return v,date_in(soup.get_text(' ',strip=True)),SPREAD,now(),'Live; first (large non-financial) table'
        raise ValueError('BBB row not found')
    except Exception as e: return 1.11,'January 2026',SPREAD,'Not fetched','Dated reference; '+str(e)

@st.cache_data(ttl=21600,show_spinner=False)
def fetch_taxes():
    try:
        r=get(OECD,headers={'Accept':'text/csv'}); f=pd.read_csv(StringIO(r.text)); f.columns=[str(c).strip().upper() for c in f.columns]
        for col,val in [('MEASURE','CIT_C'),('TARGETING','ST'),('SECTOR','S13')]:
            if col in f: f=f[f[col]==val]
        f['OBS_VALUE']=pd.to_numeric(f['OBS_VALUE'],errors='coerce'); f=f.dropna(subset=['OBS_VALUE']); f=f[f.OBS_VALUE.between(0,100)]
        f=f.sort_values('TIME_PERIOD').drop_duplicates('REF_AREA',keep='last')
        out={str(row.REF_AREA):(float(row.OBS_VALUE),str(row.TIME_PERIOD)) for row in f.itertuples()}
        if 'USA' not in out: raise ValueError('US combined statutory rate missing')
        return out,now(),'Live OECD SDMX'
    except Exception as e: return {'USA':(25.57,'2025'),'GBR':(25.,'2025')},'Not fetched','Dated OECD reference subset; '+str(e)

@st.cache_data(ttl=900,show_spinner=False)
def fetch_yield(country):
    slug=SLUGS.get(country,country.lower().replace(' ','-').replace(',',''))
    url=f'https://tradingeconomics.com/{slug}/government-bond-yield'
    try:
        try:
            r=get(url); soup=BeautifulSoup(r.text,'html.parser'); text=soup.get_text(' ',strip=True)
        except Exception:
            text='' 
        # Prefer explicit dated observation in provider prose; never parse changes/forecasts.
        pat=r'(?:held steady|increased|decreased|rose|fell|was|stood|edged up|edged down|dropped|climbed)\s+(?:by\s+[^%]+%\s+)?(?:at|to)\s+(-?\d+(?:\.\d+)?)%?\s+on\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})'
        matches=re.findall(pat,text,re.I)
        # Restrict prose to the government-bond summary if possible.
        for phrase in re.split(r'(?<=[.!?])\s+',text):
            if re.search(r'10.year|10y|10 year',phrase,re.I):
                m=re.search(pat,phrase,re.I)
                if m: return float(m.group(1)),m.group(2),url,now(),'Live country page (dated quote)'
        m=re.search(r'\bActual\s+(-?\d+(?:\.\d+)?)\b',text,re.I)
        if m: return float(m.group(1)), 'Quote date not parsed',url,now(),'Live country page (Actual)'
        # Some pages render the country table instead of the Actual card.
        r=get(BONDS); soup=BeautifulSoup(r.text,'html.parser')
        display=next((k for k,v in ALIASES.items() if v==country),country)
        for tr in soup.find_all('tr'):
            cells=[x.get_text(' ',strip=True) for x in tr.find_all('td')]
            if len(cells)>1 and norm(cells[0]) in {norm(display),norm(country)}:
                v=float(cells[1].replace('%','').replace(',','')); return v,'Quote date not parsed',BONDS,now(),'Live bonds table'
        raise ValueError('No identifiable yield quote')
    except Exception as e:
        return (5.146,'2026-11-16',url,'Not fetched','Dated reference; '+str(e)) if country=='United States' else (None,'Unavailable',url,'Not fetched',str(e))

def override(label, value, key, lo=-20.,hi=100.,step=.01):
    enabled=st.checkbox('Override '+label,value=value is None,key=key+'_toggle')
    if not enabled: return value,False
    x=st.number_input(label,min_value=lo,max_value=hi,value=float(value) if value is not None and lo<=value<=hi else None,step=step,key=key+'_value',placeholder='Enter value')
    return x,True

def main():
    st.set_page_config(page_title='International Cost of Capital',layout='wide')
    st.title('International Cost of Capital')
    st.caption('Cross-currency project valuation | nominal annual discount rates')
    if st.sidebar.button('Refresh source data',use_container_width=True): st.cache_data.clear(); st.rerun()
    with st.spinner('Loading source data…'):
        betas,bdate,burl,bfetch,bstatus=fetch_betas(); spread,sdate,surl,sfetch,sstatus=fetch_spread(); taxes,tfetch,tstatus=fetch_taxes()
    countries={c.name:c for c in pycountry.countries}; names=sorted(countries)
    with st.sidebar:
        st.header('Project assumptions')
        industry=st.selectbox('US industry',sorted(betas),index=sorted(betas).index(DEFAULT))
        country=st.selectbox('Target country / jurisdiction',names,index=names.index('United States'))
        code=countries[country].alpha_3; currencies=get_territory_currencies(countries[country].alpha_2); currency=currencies[0] if currencies else 'Local currency'
        currency=st.text_input('Target currency label',currency,key='currency_'+code)
        tax_choice=st.radio('Project tax rate used in both currencies',['United States','Selected country'],horizontal=True)
        erp=st.number_input('Equity risk premium (%)',0.,30.,6.5,.1); debt=st.slider('Debt financing (% of enterprise value)',0,99,30)
        method=st.radio('Currency conversion model',['Parity','Local CAPM'],help='Provisional: confirm with class formulas. Parity converts gross USD returns; Local CAPM uses the same numerical ERP and spread in each currency.')
    us=fetch_yield('United States'); local=us if country=='United States' else fetch_yield(country)
    taxcode='USA' if tax_choice=='United States' else code; tax0,taxdate=taxes.get(taxcode,(None,'Unavailable'))
    with st.sidebar:
        st.header('Manual overrides')
        beta,bm=override('Unlevered beta',betas[industry],'beta_'+industry,0.,10.)
        tax,tm=override('Project corporate tax (%)',tax0,'tax_'+taxcode,0.,100.)
        sp,sm=override('USD BBB spread (%)',spread,'spread',0.,100.)
        yu,um=override('US 10-year yield (%)',us[0],'us_yield')
        yl,lm=override('Target 10-year yield (%)',yu if country=='United States' and um else local[0],'local_yield_'+code)
        auto=None if yu is None or yl is None or sp is None else sp*(100+yl)/(100+yu) if method=='Parity' else sp
        ls,lso=override('Target BBB spread (%)',auto,'local_spread_'+code,0.,100.)
        if not lso: st.caption('Auto spread: '+(f'{auto:.4f}%' if auto is not None else 'Unavailable'))
    rows=[('Industry beta',beta,'Manual' if bm else bdate,burl,bfetch,bstatus),('Corporate tax',tax,'Manual' if tm else taxdate,OECD_PAGE,tfetch,tstatus),('USD BBB spread',sp,'Manual' if sm else sdate,surl,sfetch,sstatus),('US yield',yu,'Manual' if um else us[1],us[2],us[3],us[4]),('Target yield',yl,'Manual' if lm else ('Manual (linked US)' if country=='United States' and um else local[1]),local[2],local[3],local[4]),('Target BBB spread',ls,'Manual' if lso else 'Calculated','', '',method)]
    sources=pd.DataFrame(rows,columns=['Input','Value (beta or %)','Observation / effective date','Source','Fetched UTC','Fetch status'])
    if any('Not fetched' in str(x) for x in sources['Fetched UTC']): st.warning('One or more sources could not be fetched. Dated references or manual inputs are shown; inspect source status before relying on results.')
    if len(betas)<50: st.warning('Only a reference subset of industries is available. Refresh to retrieve the complete industry universe.')
    if any(v is None for v in [beta,tax,sp,yu,yl,ls]): st.info('Enter missing values using the sidebar overrides to calculate results.')
    else:
        args=(tax/100,debt/100,erp/100,yu/100,yl/100,sp/100,ls/100 if lso else None,method)
        result=calculate(beta,*args)
        left,right=st.columns(2)
        for col,suffix,label in [(left,'us','USD'),(right,'local',currency+' · '+country)]:
            with col:
                st.subheader(label); st.metric('WACC',f"{result['wacc_'+suffix]:.2%}")
                a,b=st.columns(2); a.metric('Cost of equity',f"{result['ke_'+suffix]:.2%}"); b.metric('Pre-tax cost of debt',f"{result['kd_'+suffix]:.2%}")
        st.caption(f"Levered beta: {result['beta']:.4f} | D/E: {debt/(100-debt):.4f} | Shared tax: {tax:.2f}% | Target BBB spread: {result['spread']:.4%}")
        st.bar_chart(pd.DataFrame({'USD':[result['ke_us']*100,result['kd_us']*100,result['wacc_us']*100],f'Target ({currency})':[result['ke_local']*100,result['kd_local']*100,result['wacc_local']*100]},index=['Cost of equity','Pre-tax debt cost','WACC']))
        st.subheader('All available industries')
        records=[]
        for name,bval in sorted(betas.items()):
            effective=beta if name==industry else bval; z=calculate(effective,*args)
            records.append({'Industry':name,'Unlevered beta':effective,'Levered beta':z['beta'],'USD equity (%)':100*z['ke_us'],'USD debt (%)':100*z['kd_us'],'USD WACC (%)':100*z['wacc_us'],'Target equity (%)':100*z['ke_local'],'Target debt (%)':100*z['kd_local'],'Target WACC (%)':100*z['wacc_local'],'Selected':name==industry,'Target country':country,'Target currency':currency,'Project tax (%)':tax,'ERP (%)':erp,'Debt share (%)':debt,'US yield (%)':yu,'Target yield (%)':yl,'USD BBB (%)':sp,'Target BBB (%)':100*z['spread'],'Method':method})
        df=pd.DataFrame(records); st.dataframe(df.iloc[:,:10],hide_index=True,use_container_width=True)
        c1,c2,c3=st.columns(3); c1.download_button('Download all industries CSV',df.to_csv(index=False),'industry_comparison.csv','text/csv'); c2.download_button('Download selected project CSV',df[df.Selected].to_csv(index=False),'project.csv','text/csv'); c3.download_button('Download source audit CSV',sources.to_csv(index=False),'sources.csv','text/csv')
    st.subheader('Data sources and dates'); st.dataframe(sources,hide_index=True,use_container_width=True,column_config={'Source':st.column_config.LinkColumn('Source')})
    with st.expander('Model assumptions and formulas',expanded=True):
        st.markdown('**Provisional methodology — verify against class formulas.** The same project tax, debt weight and ERP input are used in both currencies. Government yields proxy nominal risk-free rates; sovereign credit risk, FX hedging basis and explicit country risk premiums are not separately modeled. BBB spread is a benchmark, not a project-specific quote. The selected beta override applies only to the selected industry.')
        st.latex(r'\beta_L=\beta_U[1+(1-T)D/E],\quad D/E=w_D/(1-w_D)')
        st.latex(r'k_{e,USD}=y_{USD}+\beta_L ERP,\quad k_{d,USD}=y_{USD}+s_{USD}')
        if method=='Parity': st.latex(r'F=\frac{1+y_L}{1+y_{USD}},\quad k_{e,L}=(1+k_{e,USD})F-1,\quad s_L=s_{USD}F')
        else: st.latex(r'k_{e,L}=y_L+\beta_L ERP,\quad s_L=s_{USD}')
        st.latex(r'k_{d,L}=y_L+s_L,\quad WACC_c=(1-w_D)k_{e,c}+w_D k_{d,c}(1-T)')
        st.caption('Parity converts the USD equity premium implicitly; Local CAPM holds the numerical premium constant. Neither is asserted to be the instructor’s formula. Missing source coverage requires manual data.')

if __name__=='__main__': main()
