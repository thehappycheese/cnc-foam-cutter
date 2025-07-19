use heapless::String;

pub fn format_float_2dp(value: f32) -> heapless::String<16> {
   
    let mut result = String::new();
   
    // Convert to fixed point
    let scaled = value * 100.0;
    let rounded = if scaled >= 0.0 {
        (scaled + 0.5) as i32
    } else {
        (scaled - 0.5) as i32
    };
   
    let integer_part = rounded / 100;
    let fractional_part = (rounded % 100).abs();
   
    // Simple integer to string conversion
    if integer_part == 0 {
        // Check if the original rounded value was negative
        if rounded < 0 {
            result.push('-').unwrap();
        }
        result.push('0').unwrap();
    } else {
        let mut temp = integer_part;
        let mut digits = heapless::Vec::<u8, 16>::new();
       
        if temp < 0 {
            result.push('-').unwrap();
            temp = -temp;
        }
       
        while temp > 0 {
            digits.push((temp % 10) as u8 + b'0').unwrap();
            temp /= 10;
        }
       
        for &digit in digits.iter().rev() {
            result.push(digit as char).unwrap();
        }
    }
   
    result.push('.').unwrap();
   
    // Add fractional part with zero padding
    if fractional_part < 10 {
        result.push('0').unwrap();
    }
    if fractional_part == 0 {
        result.push('0').unwrap();
    } else {
        let temp = fractional_part;
        if temp < 10 {
            result.push((temp + b'0' as i32) as u8 as char).unwrap();
        } else {
            result.push(((temp / 10) + b'0' as i32) as u8 as char).unwrap();
            result.push(((temp % 10) + b'0' as i32) as u8 as char).unwrap();
        }
    }
   
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_positive_integers() {
        assert_eq!(format_float_2dp(1.0), "1.00");
        assert_eq!(format_float_2dp(42.0), "42.00");
        assert_eq!(format_float_2dp(100.0), "100.00");
    }

    #[test]
    fn test_zero() {
        assert_eq!(format_float_2dp(0.0), "0.00");
        assert_eq!(format_float_2dp(-0.0), "0.00");
    }

    #[test]
    fn test_negative_integers() {
        assert_eq!(format_float_2dp(-1.0), "-1.00");
        assert_eq!(format_float_2dp(-42.0), "-42.00");
        assert_eq!(format_float_2dp(-100.0), "-100.00");
    }

    #[test]
    fn test_positive_decimals() {
        assert_eq!(format_float_2dp(1.23), "1.23");
        assert_eq!(format_float_2dp(0.50), "0.50");
        assert_eq!(format_float_2dp(0.05), "0.05");
        assert_eq!(format_float_2dp(12.34), "12.34");
    }

    #[test]
    fn test_negative_decimals() {
        assert_eq!(format_float_2dp(-1.23), "-1.23");
        assert_eq!(format_float_2dp(-0.50), "-0.50");
        assert_eq!(format_float_2dp(-0.05), "-0.05");
        assert_eq!(format_float_2dp(-12.34), "-12.34");
    }

    #[test]
    fn test_rounding_behavior() {
        // Test rounding up
        assert_eq!(format_float_2dp(1.235), "1.24");
        assert_eq!(format_float_2dp(0.995), "1.00");
        
        // Test rounding down
        assert_eq!(format_float_2dp(1.234), "1.23");
        assert_eq!(format_float_2dp(0.994), "0.99");
        
        // Test negative rounding
        assert_eq!(format_float_2dp(-1.235), "-1.24");
        assert_eq!(format_float_2dp(-1.234), "-1.23");
    }

    #[test]
    fn test_edge_cases() {
        // Very small positive
        assert_eq!(format_float_2dp(0.01), "0.01");
        assert_eq!(format_float_2dp(0.001), "0.00");
        
        // Very small negative
        assert_eq!(format_float_2dp(-0.01), "-0.01");
        assert_eq!(format_float_2dp(-0.001), "0.00");
        
        // Large numbers
        assert_eq!(format_float_2dp(999.99), "999.99");
        assert_eq!(format_float_2dp(-999.99), "-999.99");
    }

    #[test]
    fn test_precision_boundary() {
        // Test values that stress the 2 decimal place formatting
        assert_eq!(format_float_2dp(9.99), "9.99");
        assert_eq!(format_float_2dp(10.00), "10.00");
        assert_eq!(format_float_2dp(99.99), "99.99");
        assert_eq!(format_float_2dp(100.01), "100.01");
    }
}