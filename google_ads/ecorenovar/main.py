import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient

# Load env
load_dotenv()

CUSTOMER_ID = "4411266251"

def get_ads_client():
    # 1. Tenta carregar das variáveis de ambiente (GitHub Secrets / Nuvem)
    yaml_content = os.getenv("GOOGLE_ADS_YAML")
    if yaml_content:
        return GoogleAdsClient.load_from_string(yaml_content)
        
    # 2. Tenta usar o caminho absoluto local (Windows)
    local_path = "c:/Users/VICTOR/IAS/agency/google-ads-mcp/google-ads.yaml"
    if os.path.exists(local_path):
        return GoogleAdsClient.load_from_storage(local_path)
    
    # 3. Fallback: arquivo local no mesmo diretório
    return GoogleAdsClient.load_from_storage("google-ads.yaml")

def get_guardian_insights():
    client = get_ads_client()
    ga_service = client.get_service("GoogleAdsService")
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    print(f"Gerando Insights para {CUSTOMER_ID}...")
    
    insights = []
    
    # 1. Check Search Terms for Negative Candidates (High clicks, 0 convs)
    st_query = f"""
        SELECT 
            search_term_view.search_term, 
            metrics.clicks, 
            metrics.cost_micros, 
            metrics.conversions, 
            campaign.name 
        FROM search_term_view 
        WHERE segments.date >= '{start_date}' AND segments.date <= '{end_date}'
        AND metrics.clicks > 5
        AND metrics.conversions = 0
    """
    
    try:
        response = ga_service.search(customer_id=CUSTOMER_ID, query=st_query)
        neg_candidates = []
        for r in response:
            neg_candidates.append({
                "term": r.search_term_view.search_term,
                "clicks": r.metrics.clicks,
                "cost": r.metrics.cost_micros / 1e6,
                "campaign": r.campaign.name
            })
        
        if neg_candidates:
            insights.append("🚫 *Sugestões de Negativação (Alta queima s/ Conversão):*")
            for c in sorted(neg_candidates, key=lambda x: x['cost'], reverse=True)[:5]:
                insights.append(f"• `{c['term']}`: {c['clicks']} cliques | Gasto: R${c['cost']:.2f} (Camp: {c['campaign']})")
    except Exception as e:
        insights.append(f"Erro ao buscar termos: {e}")

    # 2. Check for Performance Drops (Impression Share)
    is_query = f"""
        SELECT 
            campaign.name, 
            metrics.search_budget_lost_impression_share,
            metrics.search_rank_lost_impression_share
        FROM campaign 
        WHERE segments.date >= '{start_date}' AND segments.date <= '{end_date}'
        AND metrics.search_budget_lost_impression_share > 0.2
    """
    
    try:
        response = ga_service.search(customer_id=CUSTOMER_ID, query=is_query)
        budget_alerts = []
        for r in response:
            budget_alerts.append(f"• *{r.campaign.name}*: Perda de {r.metrics.search_budget_lost_impression_share*100:.1f}% por orçamento.")
        
        if budget_alerts:
            insights.append("\n💰 *Alertas de Orçamento:*")
            insights.extend(budget_alerts)
    except:
        pass

    # 3. Check for Low CTR / Quality Keywords
    kw_query = f"""
        SELECT 
            ad_group_criterion.keyword.text, 
            metrics.ctr, 
            ad_group_criterion.quality_info.quality_score 
        FROM keyword_view 
        WHERE segments.date >= '{start_date}' AND segments.date <= '{end_date}'
        AND metrics.impressions > 100
        AND metrics.ctr < 0.01
    """
    
    try:
        response = ga_service.search(customer_id=CUSTOMER_ID, query=kw_query)
        low_perf = []
        for r in response:
            low_perf.append(f"• `{r.ad_group_criterion.keyword.text}` (CTR: {r.metrics.ctr*100:.2f}%)")
        
        if low_perf:
            insights.append("\n📉 *Keywords com Baixo CTR (Revisar Criativos):*")
            insights.extend(low_perf[:5])
    except:
        pass

    return "\n".join(insights)

if __name__ == "__main__":
    msg = get_guardian_insights()
    if not msg:
        msg = "✅ Conta saudável! Sem anomalias detectadas nos últimos 7 dias."
    
    final_msg = f"🛡️ *GUARDIÃO ECO-RENOVAR*\nRelatório de Insights de IA\n\n{msg}\n\n⏰ *Próxima análise em 48h.*"
    print(final_msg)
    
    # Enviar para o n8n via Webhook
    # Na nuvem, isso virá das variáveis de ambiente (GitHub Secrets)
    N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "https://evolution-n8n.kpyewn.easypanel.host/webhook/ecorenovar-insights")
    
    if N8N_WEBHOOK_URL and N8N_WEBHOOK_URL != "SUA_URL_DO_WEBHOOK_N8N_AQUI":
        try:
            response = requests.post(N8N_WEBHOOK_URL, json={"text": final_msg})
            print(f"\n[+] Enviado para o n8n: Status {response.status_code}")
        except Exception as e:
            print(f"\n[-] Erro ao enviar para o n8n: {e}")
    else:
        print("\n[!] Configure a N8N_WEBHOOK_URL no script para automatizar o envio via n8n.")
