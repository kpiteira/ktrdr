"""
API fuzzy logic models tests.

This module tests the fuzzy logic models for API requests and responses.
"""
import pytest
from pydantic import ValidationError

from ktrdr.api.models.fuzzy import (
    MembershipFunctionType,
    MembershipFunction,
    FuzzyVariable,
    FuzzyRule,
    FuzzySystem,
    FuzzyConfig,
    FuzzyInput,
    FuzzyOutput
)


class TestMembershipFunction:
    """Tests for the MembershipFunction model."""
    
    def test_valid_triangular_mf(self):
        """Test that a valid triangular membership function is created correctly."""
        mf = MembershipFunction(
            type=MembershipFunctionType.TRIANGULAR,
            name="medium",
            parameters={"points": [25.0, 50.0, 75.0]}
        )
        assert mf.type == MembershipFunctionType.TRIANGULAR
        assert mf.name == "medium"
        assert mf.parameters["points"] == [25.0, 50.0, 75.0]
    
    def test_valid_trapezoidal_mf(self):
        """Test that a valid trapezoidal membership function is created correctly."""
        mf = MembershipFunction(
            type=MembershipFunctionType.TRAPEZOIDAL,
            name="normal",
            parameters={"points": [20.0, 40.0, 60.0, 80.0]}
        )
        assert mf.type == MembershipFunctionType.TRAPEZOIDAL
        assert mf.name == "normal"
        assert mf.parameters["points"] == [20.0, 40.0, 60.0, 80.0]
    
    def test_valid_gaussian_mf(self):
        """Test that a valid gaussian membership function is created correctly."""
        mf = MembershipFunction(
            type=MembershipFunctionType.GAUSSIAN,
            name="normal",
            parameters={"mean": 50.0, "sigma": 10.0}
        )
        assert mf.type == MembershipFunctionType.GAUSSIAN
        assert mf.name == "normal"
        assert mf.parameters["mean"] == 50.0
        assert mf.parameters["sigma"] == 10.0
    
    def test_invalid_triangular_mf_points(self):
        """Test that invalid triangular MF points raises validation error."""
        # Missing points parameter
        with pytest.raises(ValidationError) as exc_info:
            MembershipFunction(
                type=MembershipFunctionType.TRIANGULAR,
                name="medium",
                parameters={"wrong_key": [25.0, 50.0, 75.0]}
            )
        assert "points" in str(exc_info.value)
        
        # Wrong number of points
        with pytest.raises(ValidationError) as exc_info:
            MembershipFunction(
                type=MembershipFunctionType.TRIANGULAR,
                name="medium",
                parameters={"points": [25.0, 50.0]}  # Only 2 points
            )
        assert "3 values" in str(exc_info.value)
        
        # Points not in ascending order
        with pytest.raises(ValidationError) as exc_info:
            MembershipFunction(
                type=MembershipFunctionType.TRIANGULAR,
                name="medium",
                parameters={"points": [25.0, 75.0, 50.0]}  # Not ascending
            )
        assert "a <= b <= c" in str(exc_info.value)
    
    def test_invalid_gaussian_mf_parameters(self):
        """Test that invalid gaussian MF parameters raises validation error."""
        # Missing mean parameter
        with pytest.raises(ValidationError) as exc_info:
            MembershipFunction(
                type=MembershipFunctionType.GAUSSIAN,
                name="normal",
                parameters={"sigma": 10.0}  # Missing mean
            )
        assert "mean" in str(exc_info.value)
        
        # Negative sigma
        with pytest.raises(ValidationError) as exc_info:
            MembershipFunction(
                type=MembershipFunctionType.GAUSSIAN,
                name="normal",
                parameters={"mean": 50.0, "sigma": -10.0}  # Negative sigma
            )
        assert "sigma" in str(exc_info.value)


class TestFuzzyVariable:
    """Tests for the FuzzyVariable model."""
    
    def test_valid_fuzzy_variable(self):
        """Test that a valid fuzzy variable is created correctly."""
        variable = FuzzyVariable(
            name="temperature",
            description="Room temperature in Celsius",
            range=[0, 100],
            membership_functions=[
                MembershipFunction(
                    type=MembershipFunctionType.TRIANGULAR,
                    name="cold",
                    parameters={"points": [0, 0, 30]}
                ),
                MembershipFunction(
                    type=MembershipFunctionType.TRIANGULAR,
                    name="warm",
                    parameters={"points": [20, 50, 80]}
                ),
                MembershipFunction(
                    type=MembershipFunctionType.TRIANGULAR,
                    name="hot",
                    parameters={"points": [70, 100, 100]}
                )
            ]
        )
        assert variable.name == "temperature"
        assert variable.description == "Room temperature in Celsius"
        assert variable.range == [0, 100]
        assert len(variable.membership_functions) == 3
        assert variable.membership_functions[0].name == "cold"
        assert variable.membership_functions[1].name == "warm"
        assert variable.membership_functions[2].name == "hot"
    
    def test_invalid_range(self):
        """Test that invalid range raises validation error."""
        # Range not a list of 2 values
        with pytest.raises(ValidationError) as exc_info:
            FuzzyVariable(
                name="temperature",
                range=[0, 50, 100],  # 3 values
                membership_functions=[
                    MembershipFunction(
                        type=MembershipFunctionType.TRIANGULAR,
                        name="normal",
                        parameters={"points": [0, 50, 100]}
                    )
                ]
            )
        assert "Range must be a list with 2 values" in str(exc_info.value)
        
        # Range min >= max
        with pytest.raises(ValidationError) as exc_info:
            FuzzyVariable(
                name="temperature",
                range=[100, 0],  # Min > Max
                membership_functions=[
                    MembershipFunction(
                        type=MembershipFunctionType.TRIANGULAR,
                        name="normal",
                        parameters={"points": [0, 50, 100]}
                    )
                ]
            )
        assert "Range minimum must be less than maximum" in str(exc_info.value)
    
    def test_duplicate_mf_names(self):
        """Test that duplicate MF names raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzyVariable(
                name="temperature",
                range=[0, 100],
                membership_functions=[
                    MembershipFunction(
                        type=MembershipFunctionType.TRIANGULAR,
                        name="normal",  # Duplicate name
                        parameters={"points": [0, 25, 50]}
                    ),
                    MembershipFunction(
                        type=MembershipFunctionType.TRIANGULAR,
                        name="normal",  # Duplicate name
                        parameters={"points": [50, 75, 100]}
                    )
                ]
            )
        assert "Duplicate membership function name" in str(exc_info.value)


class TestFuzzyRule:
    """Tests for the FuzzyRule model."""
    
    def test_valid_rule(self):
        """Test that a valid fuzzy rule is created correctly."""
        rule = FuzzyRule(
            id="rule1",
            description="Temperature control rule",
            antecedent="IF temperature IS hot",
            consequent="THEN cooling IS high",
            weight=0.8
        )
        assert rule.id == "rule1"
        assert rule.description == "Temperature control rule"
        assert rule.antecedent == "IF temperature IS hot"
        assert rule.consequent == "THEN cooling IS high"
        assert rule.weight == 0.8
    
    def test_invalid_weight(self):
        """Test that invalid weight raises validation error."""
        # Weight > 1.0
        with pytest.raises(ValidationError) as exc_info:
            FuzzyRule(
                id="rule1",
                antecedent="IF temperature IS hot",
                consequent="THEN cooling IS high",
                weight=1.5  # > 1.0
            )
        assert "weight" in str(exc_info.value)
        
        # Weight < 0.0
        with pytest.raises(ValidationError) as exc_info:
            FuzzyRule(
                id="rule1",
                antecedent="IF temperature IS hot",
                consequent="THEN cooling IS high",
                weight=-0.5  # < 0.0
            )
        assert "weight" in str(exc_info.value)


class TestFuzzySystem:
    """Tests for the FuzzySystem model."""
    
    def test_valid_system(self):
        """Test that a valid fuzzy system is created correctly."""
        system = FuzzySystem(
            name="temperature_control",
            description="HVAC temperature control system",
            input_variables=[
                FuzzyVariable(
                    name="temperature",
                    range=[0, 100],
                    membership_functions=[
                        MembershipFunction(
                            type=MembershipFunctionType.TRIANGULAR,
                            name="cold",
                            parameters={"points": [0, 0, 30]}
                        ),
                        MembershipFunction(
                            type=MembershipFunctionType.TRIANGULAR,
                            name="warm",
                            parameters={"points": [20, 50, 80]}
                        )
                    ]
                )
            ],
            output_variables=[
                FuzzyVariable(
                    name="cooling",
                    range=[0, 100],
                    membership_functions=[
                        MembershipFunction(
                            type=MembershipFunctionType.TRIANGULAR,
                            name="low",
                            parameters={"points": [0, 0, 50]}
                        ),
                        MembershipFunction(
                            type=MembershipFunctionType.TRIANGULAR,
                            name="high",
                            parameters={"points": [50, 100, 100]}
                        )
                    ]
                )
            ],
            rules=[
                FuzzyRule(
                    id="rule1",
                    antecedent="IF temperature IS warm",
                    consequent="THEN cooling IS high",
                    weight=1.0
                )
            ],
            defuzzification_method="centroid"
        )
        assert system.name == "temperature_control"
        assert len(system.input_variables) == 1
        assert len(system.output_variables) == 1
        assert len(system.rules) == 1
        assert system.defuzzification_method == "centroid"
    
    def test_invalid_defuzzification_method(self):
        """Test that invalid defuzzification method raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzySystem(
                name="temperature_control",
                input_variables=[
                    FuzzyVariable(
                        name="temperature",
                        range=[0, 100],
                        membership_functions=[
                            MembershipFunction(
                                type=MembershipFunctionType.TRIANGULAR,
                                name="normal",
                                parameters={"points": [0, 50, 100]}
                            )
                        ]
                    )
                ],
                output_variables=[
                    FuzzyVariable(
                        name="cooling",
                        range=[0, 100],
                        membership_functions=[
                            MembershipFunction(
                                type=MembershipFunctionType.TRIANGULAR,
                                name="normal",
                                parameters={"points": [0, 50, 100]}
                            )
                        ]
                    )
                ],
                rules=[
                    FuzzyRule(
                        id="rule1",
                        antecedent="IF temperature IS normal",
                        consequent="THEN cooling IS normal",
                        weight=1.0
                    )
                ],
                defuzzification_method="invalid_method"  # Invalid method
            )
        assert "Defuzzification method" in str(exc_info.value)
    
    def test_duplicate_variable_names(self):
        """Test that duplicate variable names raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzySystem(
                name="temperature_control",
                input_variables=[
                    FuzzyVariable(
                        name="temperature",  # Same name in input and output
                        range=[0, 100],
                        membership_functions=[
                            MembershipFunction(
                                type=MembershipFunctionType.TRIANGULAR,
                                name="normal",
                                parameters={"points": [0, 50, 100]}
                            )
                        ]
                    )
                ],
                output_variables=[
                    FuzzyVariable(
                        name="temperature",  # Same name in input and output
                        range=[0, 100],
                        membership_functions=[
                            MembershipFunction(
                                type=MembershipFunctionType.TRIANGULAR,
                                name="normal",
                                parameters={"points": [0, 50, 100]}
                            )
                        ]
                    )
                ],
                rules=[
                    FuzzyRule(
                        id="rule1",
                        antecedent="IF temperature IS normal",
                        consequent="THEN temperature IS normal",
                        weight=1.0
                    )
                ]
            )
        assert "unique across inputs and outputs" in str(exc_info.value)