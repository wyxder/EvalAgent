import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd';
import type { EvalTask, LLMConfig, RsiCreatePayload, RsiLoop } from '../../types';
import * as api from '../../services/api';

const { Text } = Typography;

interface RsiCreateModalProps {
  open: boolean;
  baselineEvalId?: number | null;
  onClose: () => void;
  onCreated: (loop: RsiLoop) => void;
}

interface MetricOption {
  value: string;
  label: string;
}

const buildMetricOptions = (task?: EvalTask): MetricOption[] => {
  const metrics = (task?.scenario_snapshot?.metrics || []) as any[];
  const seen = new Set<string>();
  const options: MetricOption[] = [];
  metrics.forEach((item) => {
    const definition = item?.metric_definition || {};
    const name = String(definition.name || '');
    if (!name || seen.has(name)) return;
    seen.add(name);
    options.push({
      value: name,
      label: `${definition.display_name || name}（${name}）`,
    });
  });
  return options;
};

const RsiCreateModal: React.FC<RsiCreateModalProps> = ({
  open,
  baselineEvalId,
  onClose,
  onCreated,
}) => {
  const [form] = Form.useForm();
  const [evaluations, setEvaluations] = useState<EvalTask[]>([]);
  const [llmConfigs, setLlmConfigs] = useState<LLMConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const selectedBaselineId = Form.useWatch('baseline_eval_id', form) as number | undefined;
  const objectiveMode = Form.useWatch('objective_mode', form) as string | undefined;

  const selectedBaseline = useMemo(
    () => evaluations.find((item) => item.id === selectedBaselineId),
    [evaluations, selectedBaselineId],
  );
  const metricOptions = useMemo(
    () => buildMetricOptions(selectedBaseline),
    [selectedBaseline],
  );

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    Promise.all([api.listEvaluations(), api.listLLMConfigs()])
      .then(([evalData, configData]) => {
        const completed = (evalData as EvalTask[]).filter(
          (item) => item.status === 'completed' && item.scenario_snapshot,
        );
        setEvaluations(completed);
        setLlmConfigs(configData as LLMConfig[]);
        const preferred =
          baselineEvalId && completed.some((item) => item.id === baselineEvalId)
            ? baselineEvalId
            : completed[0]?.id;
        if (preferred) {
          const task = completed.find((item) => item.id === preferred);
          const options = buildMetricOptions(task);
          form.setFieldsValue({
            baseline_eval_id: preferred,
            name: `${task?.name || '评测'} · 自进化`,
            objective_metric: options[0]?.value,
          });
        }
      })
      .catch(() => message.error('加载已完成评测失败'))
      .finally(() => setLoading(false));
  }, [open, baselineEvalId, form]);

  const handleBaselineChange = (value: number) => {
    const task = evaluations.find((item) => item.id === value);
    const options = buildMetricOptions(task);
    form.setFieldsValue({
      name: `${task?.name || '评测'} · 自进化`,
      objective_metric: options[0]?.value,
    });
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: RsiCreatePayload = {
        name: values.name,
        description: values.description || null,
        baseline_eval_id: values.baseline_eval_id,
        proposer_llm_config_id: values.proposer_llm_config_id || null,
        objective_mode: values.objective_mode,
        objective_metric: values.objective_metric || null,
        objective_target: values.objective_target ?? null,
        budget: {
          max_iterations: values.max_iterations,
          max_rows_per_iteration: values.max_rows_per_iteration,
          max_llm_calls: values.max_llm_calls,
          max_minutes: values.max_minutes,
          max_proposals_per_iteration: values.max_proposals_per_iteration,
        },
        holdout: {
          holdout_ratio: values.holdout_ratio,
          min_rows: values.holdout_min_rows,
          min_rows_for_auto_accept: values.holdout_min_rows_auto,
        },
        auto_apply_low_risk: values.auto_apply_low_risk ?? false,
      };
      setSubmitting(true);
      const loop = (await api.createRsiLoop(payload)) as RsiLoop;
      message.success('RSI 循环已创建');
      form.resetFields();
      onCreated(loop);
    } catch (error: any) {
      if (error?.errorFields) return;
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : '创建 RSI 循环失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="创建 RSI 自进化循环"
      open={open}
      width={760}
      okText="创建循环"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={handleSubmit}
      onCancel={onClose}
      destroyOnClose
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="基线评测必须已完成，且已冻结 scenario_snapshot"
        description="创建后自动继承基线评测的数据集、场景、评测模式与 Judge 配置；验收阈值在创建时冻结，后续候选修改阈值不会影响验收口径。归因与提案只读取 train 切片，holdout 不进入提示词。"
      />
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          objective_mode: 'reference_pass_rate',
          max_iterations: 3,
          max_rows_per_iteration: 50,
          max_llm_calls: 300,
          max_minutes: 45,
          max_proposals_per_iteration: 3,
          holdout_ratio: 0.3,
          holdout_min_rows: 10,
          holdout_min_rows_auto: 30,
          auto_apply_low_risk: false,
        }}
      >
        <Form.Item
          name="baseline_eval_id"
          label="基线评测"
          rules={[{ required: true, message: '请选择已完成的基线评测' }]}
        >
          <Select
            showSearch
            loading={loading}
            placeholder="选择已完成的评测任务"
            optionFilterProp="label"
            onChange={handleBaselineChange}
            options={evaluations.map((item) => ({
              value: item.id,
              label: `#${item.id} ${item.name}`,
            }))}
          />
        </Form.Item>

        {selectedBaseline && (
          <Space wrap size={[8, 8]} style={{ marginBottom: 16 }}>
            <Tag color="blue">数据集 #{selectedBaseline.dataset_id}</Tag>
            <Tag color="purple">{selectedBaseline.scenario_snapshot?.name || `场景 #${selectedBaseline.scenario_id}`}</Tag>
            <Tag color={selectedBaseline.evaluation_mode === 'endpoint' ? 'orange' : 'default'}>
              {selectedBaseline.evaluation_mode === 'endpoint' ? '接口实时评测' : '已有结果评测'}
            </Tag>
            <Text type="secondary">继承 Judge 配置 #{selectedBaseline.llm_config_id}</Text>
          </Space>
        )}

        <Row gutter={16}>
          <Col span={16}>
            <Form.Item
              name="name"
              label="循环名称"
              rules={[{ required: true, message: '请输入循环名称' }]}
            >
              <Input placeholder="例如：客服 Agent 指标 Prompt 自进化" maxLength={200} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="proposer_llm_config_id" label="提案 LLM（可选）">
              <Select
                allowClear
                placeholder="默认复用 Judge"
                options={llmConfigs.map((item) => ({
                  value: item.id,
                  label: `${item.name}（${item.model_name}）`,
                }))}
              />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item name="description" label="说明">
          <Input.TextArea rows={2} maxLength={2000} placeholder="可选：记录本次自进化的目标与背景" />
        </Form.Item>

        <Divider orientation="left" plain>验收策略</Divider>
        <Row gutter={16}>
          <Col span={8}>
            <Form.Item name="objective_mode" label="目标口径" rules={[{ required: true }]}>
              <Select
                options={[
                  { value: 'reference_pass_rate', label: '冻结参考阈值的样本通过率' },
                  { value: 'metric_mean', label: '指定指标的平均分' },
                ]}
              />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item
              name="objective_metric"
              label="目标指标"
              rules={objectiveMode === 'metric_mean' ? [{ required: true, message: '请选择目标指标' }] : []}
            >
              <Select
                allowClear
                placeholder="选择基线快照中的指标"
                options={metricOptions}
              />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="objective_target" label="目标值（0~1，可选）">
              <InputNumber min={0} max={1} step={0.01} style={{ width: '100%' }} placeholder="达到后停止" />
            </Form.Item>
          </Col>
        </Row>
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="阈值无关验收"
          description="验收只看冻结参考阈值下的样本通过率或目标指标均值；候选自身调整 pass_threshold 只影响报告展示，不会机械抬高验收结果。"
        />

        <Divider orientation="left" plain>预算与 Holdout</Divider>
        <Row gutter={16}>
          <Col span={8}>
            <Form.Item name="max_iterations" label="最大轮次">
              <InputNumber min={1} max={10} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="max_rows_per_iteration" label="每轮最大行数">
              <InputNumber min={1} max={500} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="max_proposals_per_iteration" label="每轮最大提案数">
              <InputNumber min={1} max={3} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="max_llm_calls" label="最大 LLM 调用数">
              <InputNumber min={10} max={100000} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="max_minutes" label="最大运行分钟">
              <InputNumber min={1} max={600} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="holdout_ratio" label="Holdout 比例（≤0.5）">
              <InputNumber min={0} max={0.5} step={0.05} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="holdout_min_rows" label="Holdout 最少行数">
              <InputNumber min={5} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="holdout_min_rows_auto" label="自动采纳最少 Holdout 行数">
              <InputNumber min={5} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item
              name="auto_apply_low_risk"
              label="低风险自动采纳"
              valuePropName="checked"
              tooltip="默认关闭。仅当验收为 accepted、holdout 行数达标且所有提案均为 low 风险时才会自动写回。"
            >
              <Switch checkedChildren="开启" unCheckedChildren="关闭" />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Modal>
  );
};

export default RsiCreateModal;
