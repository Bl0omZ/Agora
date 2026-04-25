import { getRoleStyle } from '../../constants';
import styles from './common.module.css';

interface RoleBadgeProps {
  name: string;
}

export function RoleBadge({ name }: RoleBadgeProps) {
  const style = getRoleStyle(name);
  return (
    <span className={styles.roleBadge} style={{ background: style.background, color: style.ink }}>
      <span className={styles.roleInitial} style={{ background: style.color }}>
        {style.initial}
      </span>
      {style.label}
    </span>
  );
}
