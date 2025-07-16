pub fn format_float_2dp(value: f32) -> heapless::String<16> {
    use heapless::String;
    
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
        let mut temp = fractional_part;
        if temp < 10 {
            result.push((temp + b'0' as i32) as u8 as char).unwrap();
        } else {
            result.push(((temp / 10) + b'0' as i32) as u8 as char).unwrap();
            result.push(((temp % 10) + b'0' as i32) as u8 as char).unwrap();
        }
    }
    
    result
}