import React from 'react';
import { Button, Result, Typography } from 'antd';

const { Paragraph, Text } = Typography;

interface Props {
  children: React.ReactNode;
  /** 出错时的兜底标题，便于区分是哪个区域崩了 */
  title?: string;
  /** 是否展示错误详情（开发环境默认展示） */
  showDetail?: boolean;
}

interface State {
  error: Error | null;
  errorId: string;
}

/**
 * 全局异常边界：避免单个组件报错导致整页白屏。
 * 错误 ID 同时打印到控制台，便于与后端 requestId 对照排查。
 */
export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null, errorId: '' };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      error,
      errorId: `err-${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 8)}`,
    };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', this.state.errorId, error, info.componentStack);
  }

  private reset = () => {
    this.setState({ error: null, errorId: '' });
  };

  render() {
    const { error, errorId } = this.state;
    if (!error) return this.props.children;

    const showDetail = this.props.showDetail ?? Boolean((import.meta as any).env?.DEV);

    return (
      <Result
        status="500"
        title={this.props.title || '页面渲染出现异常'}
        subTitle="已拦截异常，其他页面不受影响。可先重试，仍失败请携带错误 ID 反馈。"
        extra={[
          <Button key="retry" type="primary" onClick={this.reset}>
            重试
          </Button>,
          <Button key="reload" onClick={() => window.location.reload()}>
            刷新页面
          </Button>,
        ]}
      >
        <Paragraph>
          <Text strong>错误 ID：</Text>
          <Text code copyable>{errorId}</Text>
        </Paragraph>
        {showDetail && (
          <Paragraph>
            <Text type="secondary">{error.message}</Text>
          </Paragraph>
        )}
      </Result>
    );
  }
}

export default ErrorBoundary;
