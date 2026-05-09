import { displayAgentName } from '../../../utils/modelName';
import styles from './AgentTag.module.css';

interface Props {
  name: string;
}

export function AgentTag({ name }: Props) {
  return (
    <span className={styles.tag} data-agent={name} title={name}>
      {displayAgentName(name)}
    </span>
  );
}
