package fit.iuh.config;

import com.pgvector.PGvector;
import org.hibernate.engine.spi.SharedSessionContractImplementor;
import org.hibernate.usertype.UserType;

import java.io.Serial;
import java.io.Serializable;
import java.sql.*;
import java.util.Arrays;

public class FloatArrayVectorType implements UserType<float[]> {

    /** JDBC type used for PostgreSQL custom/extension types (vector, hstore, etc.) */
    public static final int SQL_TYPE = Types.OTHER;

    @Override
    public int getSqlType() {
        return SQL_TYPE;
    }

    @Override
    public Class<float[]> returnedClass() {
        return float[].class;
    }

    // -------------------------------------------------------------------------
    // Equality & identity
    // -------------------------------------------------------------------------

    @Override
    public boolean equals(float[] x, float[] y) {
        return Arrays.equals(x, y);
    }

    @Override
    public int hashCode(float[] x) {
        return Arrays.hashCode(x);
    }

    // -------------------------------------------------------------------------
    // JDBC read / write
    // -------------------------------------------------------------------------

    /**
     * Reads a {@code vector} value from the {@link ResultSet} and converts it to
     * a Java {@code float[]}.
     *
     * <p>PostgreSQL returns the vector column as a string in the format
     * {@code "[1.0,2.0,...,1536.0]"}. We parse it via {@link PGvector}.
     */
    @Override
    public float[] nullSafeGet(
            ResultSet rs,
            int position,
            SharedSessionContractImplementor session,
            Object owner) throws SQLException {

        String value = rs.getString(position);
        if (value == null) {
            return null;
        }
        try {
            PGvector pgVector = new PGvector(value);
            return pgVector.toArray();
        } catch (SQLException e) {
            throw new SQLException(
                    "Failed to parse pgvector string from database column at position " + position, e);
        }
    }

    /**
     * Writes a Java {@code float[]} to the {@link PreparedStatement} as a
     * PostgreSQL {@code vector} object via {@link PGvector}.
     */
    @Override
    public void nullSafeSet(
            PreparedStatement st,
            float[] value,
            int index,
            SharedSessionContractImplementor session) throws SQLException {

        if (value == null) {
            st.setNull(index, SQL_TYPE);
        } else {
            PGvector pgVector = new PGvector(value);
            st.setObject(index, pgVector);
        }
    }

    // -------------------------------------------------------------------------
    // Lifecycle & caching
    // -------------------------------------------------------------------------

    @Override
    public float[] deepCopy(float[] value) {
        if (value == null) return null;
        return Arrays.copyOf(value, value.length);
    }

    @Override
    public boolean isMutable() {
        return true;
    }

    @Override
    public Serializable disassemble(float[] value) {
        return deepCopy(value);
    }

    @Override
    public float[] assemble(Serializable cached, Object owner) {
        return deepCopy((float[]) cached);
    }
}
