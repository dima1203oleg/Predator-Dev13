"""
PostgreSQL Outbox Pattern Implementation
"""
import os
from typing import Dict, Any, List

# Outbox table schema
OUTBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS public.outbox (
    id BIGSERIAL PRIMARY KEY,
    aggregate_type VARCHAR(255) NOT NULL,
    aggregate_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    processed BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_outbox_processed_created ON public.outbox (processed, created_at);
CREATE INDEX IF NOT EXISTS idx_outbox_aggregate ON public.outbox (aggregate_type, aggregate_id);
CREATE INDEX IF NOT EXISTS idx_outbox_event_type ON public.outbox (event_type);

-- Partitioning by month for large volumes
-- CREATE TABLE public.outbox_y2024m01 PARTITION OF public.outbox FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
"""

# Trigger functions for automatic outbox events
OUTBOX_TRIGGERS = {
    "customs_data": """
CREATE OR REPLACE FUNCTION public.outbox_customs_data()
RETURNS TRIGGER AS $$
DECLARE
    event_type TEXT;
    payload JSONB;
BEGIN
    -- Determine event type
    IF TG_OP = 'INSERT' THEN
        event_type := 'customs_data.created';
        payload := jsonb_build_object(
            'id', NEW.id,
            'hs_code', NEW.hs_code,
            'company_name', NEW.company_name,
            'edrpou', NEW.edrpou,
            'amount', NEW.amount,
            'date', NEW.date,
            'country_code', NEW.country_code,
            'customs_office', NEW.customs_office,
            'op_hash', NEW.op_hash,
            'created_at', NEW.created_at
        );
    ELSIF TG_OP = 'UPDATE' THEN
        event_type := 'customs_data.updated';
        payload := jsonb_build_object(
            'id', NEW.id,
            'old_data', jsonb_build_object(
                'hs_code', OLD.hs_code,
                'company_name', OLD.company_name,
                'amount', OLD.amount
            ),
            'new_data', jsonb_build_object(
                'hs_code', NEW.hs_code,
                'company_name', NEW.company_name,
                'amount', NEW.amount
            ),
            'updated_at', NEW.updated_at
        );
    ELSIF TG_OP = 'DELETE' THEN
        event_type := 'customs_data.deleted';
        payload := jsonb_build_object(
            'id', OLD.id,
            'hs_code', OLD.hs_code,
            'company_name', OLD.company_name,
            'deleted_at', NOW()
        );
    END IF;

    -- Insert into outbox
    INSERT INTO public.outbox (aggregate_type, aggregate_id, event_type, payload)
    VALUES ('customs_data', NEW.id::TEXT, event_type, payload);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trigger_outbox_customs_data ON public.customs_data;
CREATE TRIGGER trigger_outbox_customs_data
    AFTER INSERT OR UPDATE OR DELETE ON public.customs_data
    FOR EACH ROW EXECUTE FUNCTION public.outbox_customs_data();
""",

    "companies": """
CREATE OR REPLACE FUNCTION public.outbox_companies()
RETURNS TRIGGER AS $$
DECLARE
    event_type TEXT;
    payload JSONB;
BEGIN
    IF TG_OP = 'INSERT' THEN
        event_type := 'company.created';
        payload := jsonb_build_object(
            'edrpou', NEW.edrpou,
            'name', NEW.name,
            'country', NEW.country,
            'risk_score', NEW.risk_score,
            'created_at', NEW.created_at
        );
    ELSIF TG_OP = 'UPDATE' THEN
        event_type := 'company.updated';
        payload := jsonb_build_object(
            'edrpou', NEW.edrpou,
            'old_risk_score', OLD.risk_score,
            'new_risk_score', NEW.risk_score,
            'updated_at', NEW.updated_at
        );
    END IF;

    INSERT INTO public.outbox (aggregate_type, aggregate_id, event_type, payload)
    VALUES ('company', NEW.edrpou, event_type, payload);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_outbox_companies ON public.companies;
CREATE TRIGGER trigger_outbox_companies
    AFTER INSERT OR UPDATE ON public.companies
    FOR EACH ROW EXECUTE FUNCTION public.outbox_companies();
""",

    "hs_codes": """
CREATE OR REPLACE FUNCTION public.outbox_hs_codes()
RETURNS TRIGGER AS $$
DECLARE
    event_type TEXT;
    payload JSONB;
BEGIN
    IF TG_OP = 'INSERT' THEN
        event_type := 'hs_code.created';
        payload := jsonb_build_object(
            'code', NEW.code,
            'description', NEW.description,
            'category', NEW.category,
            'duty_rate', NEW.duty_rate,
            'created_at', NEW.created_at
        );
    END IF;

    INSERT INTO public.outbox (aggregate_type, aggregate_id, event_type, payload)
    VALUES ('hs_code', NEW.code, event_type, payload);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_outbox_hs_codes ON public.hs_codes;
CREATE TRIGGER trigger_outbox_hs_codes
    AFTER INSERT ON public.hs_codes
    FOR EACH ROW EXECUTE FUNCTION public.outbox_hs_codes();
"""
}

# Outbox processing functions
OUTBOX_PROCESSING = """
-- Function to mark events as processed
CREATE OR REPLACE FUNCTION public.mark_outbox_processed(event_ids BIGINT[])
RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER;
BEGIN
    UPDATE public.outbox
    SET processed = TRUE, processed_at = NOW()
    WHERE id = ANY(event_ids) AND processed = FALSE;

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

-- Function to handle failed processing
CREATE OR REPLACE FUNCTION public.mark_outbox_failed(event_id BIGINT, error_msg TEXT)
RETURNS VOID AS $$
BEGIN
    UPDATE public.outbox
    SET retry_count = retry_count + 1,
        error_message = error_msg,
        processed_at = NOW()
    WHERE id = event_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get unprocessed events
CREATE OR REPLACE FUNCTION public.get_unprocessed_events(batch_size INTEGER DEFAULT 1000)
RETURNS TABLE (
    id BIGINT,
    aggregate_type VARCHAR(255),
    aggregate_id VARCHAR(255),
    event_type VARCHAR(255),
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        o.id,
        o.aggregate_type,
        o.aggregate_id,
        o.event_type,
        o.payload,
        o.created_at,
        o.retry_count
    FROM public.outbox o
    WHERE o.processed = FALSE
      AND (o.retry_count < 3 OR o.retry_count IS NULL)
    ORDER BY o.created_at ASC
    LIMIT batch_size
    FOR UPDATE SKIP LOCKED;
END;
$$ LANGUAGE plpgsql;
"""

# Monitoring queries
OUTBOX_MONITORING = {
    "pending_events": """
        SELECT
            aggregate_type,
            event_type,
            COUNT(*) as count,
            MIN(created_at) as oldest,
            MAX(created_at) as newest,
            AVG(EXTRACT(EPOCH FROM (NOW() - created_at))) as avg_age_seconds
        FROM public.outbox
        WHERE processed = FALSE
        GROUP BY aggregate_type, event_type
        ORDER BY count DESC;
    """,

    "processing_stats": """
        SELECT
            processed,
            COUNT(*) as total,
            AVG(retry_count) as avg_retries,
            COUNT(CASE WHEN retry_count > 0 THEN 1 END) as failed_events,
            MIN(created_at) as oldest_unprocessed
        FROM public.outbox
        GROUP BY processed;
    """,

    "event_lag": """
        SELECT
            EXTRACT(EPOCH FROM (NOW() - MIN(created_at))) as max_lag_seconds,
            COUNT(*) as pending_count
        FROM public.outbox
        WHERE processed = FALSE
          AND created_at < NOW() - INTERVAL '1 minute';
    """
}

def get_outbox_schema() -> str:
    """Get outbox table creation SQL"""
    return OUTBOX_SCHEMA

def get_outbox_triggers() -> Dict[str, str]:
    """Get trigger creation SQL for all tables"""
    return OUTBOX_TRIGGERS

def get_outbox_processing() -> str:
    """Get outbox processing functions"""
    return OUTBOX_PROCESSING

def get_monitoring_queries() -> Dict[str, str]:
    """Get monitoring queries"""
    return OUTBOX_MONITORING
